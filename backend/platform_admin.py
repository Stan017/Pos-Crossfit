"""
Auth del superadmin de la plataforma (dueño de DarkCross, no de un gym).

Separado de auth.py: ese módulo es JWT + gym_id (tenancy de un gym), esto es
una clave estática de servidor sin tenant — dos mecanismos de auth distintos
que no deben mezclarse. Usado por suscripciones.py (admin_router) y
admin_analytics.py.
"""
import os
import secrets
import logging
import time
from collections import defaultdict, deque
from uuid import UUID

from fastapi import Header, HTTPException, Request, status

from database import SessionLocal

logger = logging.getLogger("crossfit_saas")

# ── Rate-limit de intentos fallidos ─────────────────────────────────────────
#
# @limiter.limit(...) en las rutas (admin_analytics.py, suscripciones.py) NO
# alcanza para esto: es un decorador sobre el cuerpo de la ruta, y esta
# función corre ANTES como dependencia — si la clave es incorrecta, la
# excepción sale de acá y el decorador nunca llega a ejecutarse. Sin esto,
# un intento de fuerza bruta contra la clave no tenía ningún límite real.
#
# En memoria del proceso, por IP, con ventana deslizante — mismo criterio de
# almacenamiento que usa slowapi acá (sin Redis ni nada persistente). No es
# un bloqueo permanente: pasado el minuto, se libera solo. 10 intentos/min es
# generoso a propósito — deja margen para que el dueño real se equivoque
# tipeando un par de veces sin quedar afuera, pero frena cualquier intento
# automatizado de adivinar la clave.

_VENTANA_SEGUNDOS       = 60
_MAX_INTENTOS_FALLIDOS  = 10

_intentos_fallidos: dict[str, deque] = defaultdict(deque)


def _limpiar_viejos(intentos: deque, ahora: float) -> None:
    while intentos and ahora - intentos[0] > _VENTANA_SEGUNDOS:
        intentos.popleft()


def require_platform_admin(request: Request, x_platform_key: str = Header(...)):
    ip = request.client.host if request.client else "desconocida"
    ahora = time.monotonic()
    intentos = _intentos_fallidos[ip]
    _limpiar_viejos(intentos, ahora)

    if len(intentos) >= _MAX_INTENTOS_FALLIDOS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Esperá un minuto e intentá de nuevo.",
        )

    clave = os.getenv("PLATFORM_ADMIN_KEY", "")
    if not clave:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Panel de plataforma no configurado en el servidor.",
        )
    if not secrets.compare_digest(x_platform_key, clave):
        intentos.append(ahora)
        logger.warning(f"Intento fallido de X-Platform-Key desde {ip} contra {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clave de plataforma inválida.",
        )


def get_db_platform_admin(gym_id: UUID, request: Request):
    """
    Sesión DB para mutaciones del superadmin sobre un gym puntual (gym_id en
    la URL). No usa get_db_tenant: estas rutas no tienen JWT de gym y deben
    poder operar sobre cualquier gym, no quedar fijadas a uno solo vía RLS.

    Guarda el contexto en session.info (no en un contextvar — ver el
    comentario largo en database.py sobre por qué eso no funciona con cómo
    FastAPI resuelve dependencias generadoras). "rls_gym_id" scopea esta
    mutación puntual al gym de la URL vía RLS (aunque gimnasios/pagos_saas,
    las únicas tablas que tocan estas rutas, no tienen RLS igual); los otros
    dos alimentan el audit log.

    audit_usuario_id va en None, no un string tipo "platform-admin": la
    columna audit_log.usuario_id es UUID (documentado en la 002: "NULL si
    fue el sistema") — no hay una fila de Usuario real detrás de la clave
    compartida de plataforma, así que no hay un UUID legítimo que poner acá.
    Iba un string literal antes y nunca se notó porque el contextvar roto
    nunca llegaba a ejecutar el INSERT; ahora que sí llega, un string ahí
    rompería el commit entero con un error de tipo.
    """
    ip = request.client.host if request.client else None

    db = SessionLocal()
    db.info["rls_gym_id"]      = str(gym_id)
    db.info["audit_gym_id"]    = str(gym_id)
    db.info["audit_usuario_id"] = None
    db.info["audit_ip"]        = ip
    try:
        yield db
    finally:
        db.close()
