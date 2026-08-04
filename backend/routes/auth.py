import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import date, timedelta

from database import get_db, get_db_platform, set_rls_gym_id
from models import Gimnasio, Usuario, RolUsuario, VerticalNegocio
from security import sanitizar
from auth import (
    crear_access_token,
    crear_refresh_token_y_guardar,
    rotar_refresh_token,
    revocar_refresh_token,
    set_auth_cookies,
    clear_auth_cookies,
    get_usuario_actual,
    UsuarioActual,
    COOKIE_REFRESH,
)
from limiter import limiter

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash fijo sin cuenta real detrás. Se verifica contra él cuando el gimnasio
# o el usuario no existen, para que login tarde lo mismo en los tres casos
# de fallo (gym inválido, email inválido, password incorrecto) y no se
# puedan enumerar gym_slugs/emails válidos por tiempo de respuesta.
_DUMMY_HASH = pwd_context.hash("no-existe-ninguna-cuenta-con-este-password")

_SLUG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginInput(BaseModel):
    email:    EmailStr
    password: str
    gym_slug: str
    vertical: VerticalNegocio

class RegisterGymInput(BaseModel):
    gym_nombre:             str
    gym_slug:               str
    gym_email:              EmailStr
    admin_nombre:           str
    admin_apellido:         str
    admin_fecha_nacimiento: date
    admin_email:            EmailStr
    admin_password:         str
    vertical:               VerticalNegocio

    @field_validator("gym_nombre", "admin_nombre", "admin_apellido", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)

    @field_validator("gym_slug")
    @classmethod
    def slug_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError("El slug solo puede tener minúsculas, números y guiones (ej: mi-box).")
        return v

    @field_validator("admin_password")
    @classmethod
    def password_minimo(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return v

class UsuarioInfo(BaseModel):
    nombre:     str
    apellido:   str = ""
    rol:        str
    gym_nombre: str = ""


def _info_usuario(usuario: Usuario, gimnasio: Gimnasio | None) -> UsuarioInfo:
    return UsuarioInfo(
        nombre=usuario.nombre,
        apellido=usuario.apellido or "",
        rol=usuario.rol.value,
        gym_nombre=gimnasio.nombre if gimnasio else "",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=UsuarioInfo)
@limiter.limit("10/minute")
def login(
    request: Request, response: Response, datos: LoginInput,
    db:           Session = Depends(get_db),
    db_platform:  Session = Depends(get_db_platform),
):
    # gimnasios tiene RLS por id (migración 032) — buscar por slug es
    # justamente cómo se DESCUBRE el gym_id, no hay uno todavía que fijar.
    # db_platform (rol app_platform, bypassea RLS a propósito) es la única
    # forma de resolver esto; el resto del login sigue en `db` con RLS real.
    gimnasio = db_platform.query(Gimnasio).filter(
        Gimnasio.slug == datos.gym_slug,
        Gimnasio.activo == True,
    ).first()

    usuario = None
    if gimnasio:
        # Recién acá se conoce el gym_id — usuarios tiene RLS (migración 031)
        # y todavía no hay JWT en este punto del flujo para que get_db_tenant
        # lo hubiera fijado solo.
        set_rls_gym_id(db, gimnasio.id)
        usuario = db.query(Usuario).filter(
            Usuario.gym_id == gimnasio.id,
            Usuario.email  == datos.email,
            Usuario.activo == True,
        ).first()

    password_hash   = usuario.password_hash if usuario else _DUMMY_HASH
    password_valida = pwd_context.verify(datos.password, password_hash)

    # vertical viene fijo por build (frontend/ manda 'crossfit', frontend-rehab/
    # manda 'medico'), no lo elige el usuario. Si no coincide con el gimnasio
    # real, cae en el mismo 401 genérico que credenciales inválidas — un
    # mensaje distinto ("este gimnasio no es de esta plataforma") le regalaría
    # a cualquiera que pruebe slugs al azar la confirmación de que el slug
    # existe, solo que en el otro vertical.
    vertical_valida = gimnasio is not None and gimnasio.vertical == datos.vertical

    if not gimnasio or not usuario or not password_valida or not vertical_valida:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")

    set_auth_cookies(
        response,
        crear_access_token(usuario),
        crear_refresh_token_y_guardar(usuario, db),
    )
    return _info_usuario(usuario, gimnasio)


@router.post("/refresh", response_model=UsuarioInfo)
@limiter.limit("30/minute")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token_plano = request.cookies.get(COOKIE_REFRESH)
    if not token_plano:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No hay sesión activa.")

    usuario, nuevo_refresh = rotar_refresh_token(token_plano, db)
    set_auth_cookies(response, crear_access_token(usuario), nuevo_refresh)

    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    return _info_usuario(usuario, gimnasio)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token_plano = request.cookies.get(COOKIE_REFRESH)
    if token_plano:
        revocar_refresh_token(token_plano, db)
    clear_auth_cookies(response)


@router.get("/me", response_model=UsuarioInfo)
def me(
    usuario_actual: UsuarioActual = Depends(get_usuario_actual),
    db:             Session       = Depends(get_db),
):
    """Confirma si la cookie de sesión sigue siendo válida y devuelve los datos a mostrar."""
    # gym_id ya se conoce por el JWT (usuario_actual) — get_db acá no pasa por
    # get_db_tenant, así que hay que fijarlo a mano antes de tocar Usuario.
    set_rls_gym_id(db, usuario_actual.gym_id)
    usuario = db.query(Usuario).filter(
        Usuario.id == usuario_actual.user_id,
        Usuario.activo == True,
    ).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado.")

    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    return _info_usuario(usuario, gimnasio)


@router.post("/register-gym", response_model=UsuarioInfo, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register_gym(
    request: Request, response: Response, datos: RegisterGymInput,
    db:           Session = Depends(get_db),
    db_platform:  Session = Depends(get_db_platform),
):
    # Mismo motivo que en login(): gimnasios tiene RLS por id (migración 032)
    # y estos dos chequeos son de unicidad GLOBAL — tienen que ver todos los
    # gimnasios de la plataforma, no uno solo. db_platform bypassea RLS a
    # propósito para esto; el resto de la función sigue en `db` con RLS real.
    if db_platform.query(Gimnasio).filter(Gimnasio.slug == datos.gym_slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El slug ya está en uso.")
    if db_platform.query(Gimnasio).filter(Gimnasio.email == datos.gym_email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email del gimnasio ya está registrado.")

    _TRIAL_DIAS = 10
    # El default=uuid.uuid4 de la columna Gimnasio.id lo aplica SQLAlchemy
    # recién al compilar el INSERT (dentro del flush), no al construir el
    # objeto — gimnasio.id sería None acá todavía. Generarlo a mano y pasarlo
    # explícito es la única forma de conocerlo ANTES del INSERT, que es
    # justo lo que hace falta para fijar el contexto RLS antes de escribir.
    gimnasio_id = uuid.uuid4()
    gimnasio = Gimnasio(
        id               = gimnasio_id,
        nombre           = datos.gym_nombre,
        slug             = datos.gym_slug,
        email            = datos.gym_email,
        vertical         = datos.vertical,
        saas_trial_hasta = date.today() + timedelta(days=_TRIAL_DIAS),
    )
    # gimnasios tiene RLS ahora (migración 032) — el INSERT de abajo tiene
    # que cumplir el WITH CHECK igual que el de usuarios más abajo.
    set_rls_gym_id(db, gimnasio_id)
    db.add(gimnasio)
    db.flush()  # persiste el gimnasio antes del INSERT de admin (FK)

    admin = Usuario(
        gym_id=gimnasio.id,
        email=datos.admin_email,
        password_hash=pwd_context.hash(datos.admin_password),
        nombre=datos.admin_nombre,
        apellido=datos.admin_apellido,
        fecha_nacimiento=datos.admin_fecha_nacimiento,
        rol=RolUsuario.admin,
    )
    db.add(admin)
    try:
        db.commit()
    except IntegrityError as e:
        # El pre-check de arriba no cierra la carrera entre dos registros
        # simultáneos con el mismo slug/email — esto atrapa esa carrera en
        # vez de dejar pasar un 500 con el error crudo de Postgres.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese slug o email ya está en uso.",
        ) from e
    db.refresh(admin)

    set_auth_cookies(
        response,
        crear_access_token(admin),
        crear_refresh_token_y_guardar(admin, db),
    )
    return _info_usuario(admin, gimnasio)
