"""
Autenticación JWT y dependencias de sesión para CrossFit SaaS.

Access token:  JWT HS256, vida 30min, payload = { sub, gym_id, rol }
Refresh token: string aleatorio, guardado como SHA-256 en DB, vida 30d

Uso en rutas protegidas:
    from auth import get_usuario_actual
    @router.get("/ruta")
    def mi_ruta(usuario = Depends(get_usuario_actual)):
        gym_id = usuario.gym_id
"""
import os
import hashlib
import secrets
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from database import SessionLocal, ES_LOCAL, set_rls_gym_id
from models import Usuario, RefreshToken, Gimnasio, SaasEstado
from services.suscripciones_service import sincronizar_estado_saas_en_db

JWT_SECRET    = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# 30 min y no 8h: get_usuario_actual valida el JWT solo por firma/expiración,
# nunca vuelve a mirar la DB — desactivar un usuario o suspender un gym no
# tiene efecto hasta que el access token expire. Achicar la ventana es la
# mitigación estándar sin perder el punto de usar JWT (nada de consultar la
# DB en cada request): el refresh, que SÍ revalida activo/gimnasio contra la
# DB, ya corre solo y en silencio desde el frontend cuando el access vence.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))

# Ventana de gracia para rotar un refresh token ya usado: absorbe la carrera
# de dos pestañas refrescando casi al mismo tiempo (una gana, la otra presenta
# el token recién rotado). No debilita el "un solo uso" contra robo de token
# real — un token robado y usado hace más de 10s de la rotación legítima sigue
# rechazándose.
REFRESH_TOKEN_GRACIA_SEGUNDOS = 10

# No hay scheduler/cron en este proyecto (y el destino de deploy todavía no
# está decidido, así que tampoco hay dónde colgar uno) — la purga de tokens
# vencidos se engancha al punto de mayor tráfico natural sobre esta tabla:
# rotar_refresh_token(), que se dispara sola desde el frontend cada ~30min
# por cada sesión abierta. Con baja probabilidad para no sumar una query de
# limpieza en el hot path de sesión de todo el mundo, todo el tiempo.
REFRESH_TOKEN_LIMPIEZA_PROBABILIDAD = 0.01

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET no está configurado en las variables de entorno.")

# ── Cookies de sesión ──────────────────────────────────────────────────────────
# httpOnly: JS no puede leerlas — cierra el robo de token vía XSS.
# SameSite=Lax + un solo origen (todo local por ahora): el navegador ya no manda
# la cookie en un POST/PUT/DELETE disparado desde otro sitio, así que esto solo
# ya cubre CSRF sin necesitar verificación de Origin. Si más adelante backend y
# frontend quedan en dominios distintos, esto hay que revisarlo (SameSite=None
# exige verificación de Origin aparte porque deja de proteger contra CSRF solo).
#
# DECISIÓN PENDIENTE (no confundir con "ya está resuelto"): backend/.env.example
# ya tiene FRONTEND_ORIGINS apuntando a un dominio vercel.app distinto del
# backend. Si se despliega así tal cual, el supuesto de "un solo origen" de
# arriba queda roto — y no es un problema "menos seguro", es que el navegador
# directamente deja de mandar cf_access/cf_refresh en los fetch del frontend
# (SameSite=Lax bloquea XHR/fetch cross-site sin excepción). Antes de deployar
# a producción, resolver esto por una de dos vías, no una mezcla:
#   (a) el frontend hace proxy/rewrite de /api/* hacia el backend → mismo
#       origen para el navegador, esto no se toca.
#   (b) dominios realmente distintos → SameSite="none", secure=True siempre
#       (ya no solo en no-ES_LOCAL), y agregar verificación de Origin/Referer
#       en un middleware para requests que cambian estado, reemplazando la
#       protección CSRF que Lax daba gratis.

COOKIE_ACCESS  = "cf_access"
COOKIE_REFRESH = "cf_refresh"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=COOKIE_ACCESS,
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not ES_LOCAL,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=COOKIE_REFRESH,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=not ES_LOCAL,
        samesite="lax",
        # path="/" y no "/auth": el path que el navegador ve para este mismo
        # endpoint cambia según el entorno (en dev pasa por el proxy de Vite
        # como /api/auth/refresh; en producción pega directo a /auth/refresh,
        # sin prefijo /api). Un Path angosto matchea en un entorno y no en el
        # otro — con "/auth" el refresh nunca llegaba a andar en desarrollo,
        # porque el navegador jamás adjuntaba la cookie a /api/auth/refresh.
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=COOKIE_ACCESS, path="/")
    response.delete_cookie(key=COOKIE_REFRESH, path="/")


# ── Helpers de token ──────────────────────────────────────────────────────────

def crear_access_token(usuario: Usuario) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub":    str(usuario.id),
        "gym_id": str(usuario.gym_id),
        "rol":    usuario.rol.value,
        "exp":    expira,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _generar_refresh_token(usuario: Usuario, db: Session) -> str:
    """Agrega la fila de RefreshToken a la sesión, sin commitear."""
    token_plano = secrets.token_urlsafe(64)
    token_hash  = hashlib.sha256(token_plano.encode()).hexdigest()
    expira      = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db.add(RefreshToken(
        usuario_id=usuario.id,
        gym_id=usuario.gym_id,
        token_hash=token_hash,
        expira_en=expira,
    ))
    return token_plano


def crear_refresh_token_y_guardar(usuario: Usuario, db: Session) -> str:
    """Para login/registro: crea el refresh token y lo commitea de una, no hay
    nada más que deba entrar en la misma transacción."""
    token_plano = _generar_refresh_token(usuario, db)
    db.commit()
    return token_plano


def rotar_refresh_token(token_plano: str, db: Session) -> tuple[Usuario, str]:
    """
    Valida el refresh token y emite uno nuevo. Retorna (usuario, nuevo_token).

    El token presentado no se borra al rotar — se marca con usado_en y sigue
    aceptándose por REFRESH_TOKEN_GRACIA_SEGUNDOS más. Sin esto, dos pestañas
    que refrescan casi al mismo tiempo compiten por el mismo token: la que
    pierde la carrera presenta un token que la otra ya rotó, recibe 401 y
    cierra sesión sola aunque el usuario tenga una sesión válida en la otra
    pestaña. Cada request dentro de la ventana de gracia recibe SU PROPIO
    token nuevo — ninguna pestaña reutiliza el token de la otra.
    """
    token_hash = hashlib.sha256(token_plano.encode()).hexdigest()
    registro   = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not registro:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido.")

    ahora = datetime.now(timezone.utc)

    if registro.expira_en.replace(tzinfo=timezone.utc) < ahora:
        db.delete(registro)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado.")

    if registro.usado_en is not None:
        segundos_desde_uso = (ahora - registro.usado_en.replace(tzinfo=timezone.utc)).total_seconds()
        if segundos_desde_uso > REFRESH_TOKEN_GRACIA_SEGUNDOS:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido.")
        # Dentro de la ventana: se acepta, pero no se reescribe usado_en — si
        # se hiciera, cada reintento estiraría la ventana de gracia de nuevo.

    # registro.gym_id (denormalizado en la 030) es lo único que permite esta
    # consulta a Usuario bajo RLS: acá todavía no hay JWT ni gym_id conocido
    # por otra vía — es justamente lo que esta fila de RefreshToken revela.
    set_rls_gym_id(db, registro.gym_id)
    usuario = db.query(Usuario).filter(Usuario.id == registro.usuario_id).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o no encontrado.")

    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    if not gimnasio or not gimnasio.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El gimnasio está desactivado.")

    if registro.usado_en is None:
        registro.usado_en = ahora
    nuevo_token = _generar_refresh_token(usuario, db)

    if random.random() < REFRESH_TOKEN_LIMPIEZA_PROBABILIDAD:
        _purgar_refresh_tokens_vencidos(db)

    db.commit()

    return usuario, nuevo_token


def _purgar_refresh_tokens_vencidos(db: Session) -> None:
    """
    Borra filas de RefreshToken que ya no sirven para nada: vencidas por
    expira_en, o ya rotadas y fuera de la ventana de gracia (pasado ese punto
    rotar_refresh_token las rechaza igual — dejarlas en la tabla no protege
    nada, solo la hace crecer sin límite). Sin gym_id: esta sesión (get_db,
    no get_db_tenant) corre antes de que exista contexto de tenant, así que
    no hay RLS que filtre — es intencional, es una purga global de mantenimiento.
    """
    ahora         = datetime.now(timezone.utc)
    limite_gracia = ahora - timedelta(seconds=REFRESH_TOKEN_GRACIA_SEGUNDOS)
    db.query(RefreshToken).filter(
        or_(
            RefreshToken.expira_en < ahora,
            and_(RefreshToken.usado_en.isnot(None), RefreshToken.usado_en < limite_gracia),
        )
    ).delete(synchronize_session=False)


def revocar_refresh_token(token_plano: str, db: Session) -> None:
    token_hash = hashlib.sha256(token_plano.encode()).hexdigest()
    registro   = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if registro:
        db.delete(registro)
        db.commit()


# ── Dependencia principal ─────────────────────────────────────────────────────

class UsuarioActual:
    """Datos del usuario extraídos del JWT. Se inyecta en cada ruta protegida."""
    def __init__(self, user_id: str, gym_id: str, rol: str):
        self.user_id = user_id
        self.gym_id  = gym_id
        self.rol     = rol

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"


def get_usuario_actual(request: Request) -> UsuarioActual:
    credencial_invalida = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado.",
    )
    token = request.cookies.get(COOKIE_ACCESS)
    if not token:
        raise credencial_invalida
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        gym_id:  Optional[str] = payload.get("gym_id")
        rol:     Optional[str] = payload.get("rol")
        if not user_id or not gym_id or not rol:
            raise credencial_invalida
    except JWTError as e:
        # from e: el detail que ve el cliente sigue siendo el genérico de
        # credencial_invalida (no se filtra nada), pero el log del backend
        # queda con la causa real (token expirado vs. malformado vs.
        # manipulado) en vez de perder la cadena.
        raise credencial_invalida from e

    return UsuarioActual(user_id=user_id, gym_id=gym_id, rol=rol)


def get_db_tenant(
    request: Request,
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """
    Dependencia DB con contexto RLS y audit log.

    Guarda gym_id/usuario_id/ip en session.info — NO en un contextvar (ver
    el comentario largo en database.py: un ContextVar.set() hecho acá nunca
    es visible en el cuerpo de la ruta, porque FastAPI resuelve esta
    dependencia y llama a la ruta en dos llamadas separadas a
    run_in_threadpool). session.info sí viaja bien porque es parte del
    objeto `db` que se devuelve normalmente.

    "rls_gym_id" lo lee el listener de "after_begin" en database.py, en cada
    transacción de esta sesión (la primera, y cualquiera que el ORM abra
    después de un commit). Los otros tres los lee el listener de
    "after_flush" en audit.py.
    """
    ip = request.client.host if request.client else None

    db = SessionLocal()
    db.info["rls_gym_id"]     = str(usuario.gym_id)
    db.info["audit_gym_id"]   = str(usuario.gym_id)
    db.info["audit_usuario_id"] = str(usuario.user_id)
    db.info["audit_ip"]       = ip
    try:
        yield db
    finally:
        db.close()


def require_admin(usuario: UsuarioActual = Depends(get_usuario_actual)) -> UsuarioActual:
    if not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador.",
        )
    return usuario


# ── Enforcement de suscripción SaaS ──────────────────────────────────────────
# La máquina de estados de billing vive en services/suscripciones_service.py.
# Esto es solo el gate: ¿el gym puede pasar, o lo bloqueamos con 402?

def require_gym_activa(
    usuario: UsuarioActual = Depends(get_usuario_actual),
    db:      Session       = Depends(get_db_tenant),
) -> UsuarioActual:
    """Verifica que el gym tenga suscripción vigente. Bloquea con 402 si no."""
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Gimnasio no encontrado.")

    saas_estado = sincronizar_estado_saas_en_db(gimnasio, db)

    if saas_estado in (SaasEstado.vencida, SaasEstado.suspendida):
        raise HTTPException(
            status_code=402,
            detail="Suscripción vencida o suspendida. Renueva en /suscripciones/solicitar.",
        )

    return usuario
