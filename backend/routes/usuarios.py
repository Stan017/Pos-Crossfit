from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from uuid import UUID
from datetime import datetime

from models import Usuario, RolUsuario, Gimnasio
from auth import require_admin, UsuarioActual, get_db_tenant
from security import sanitizar
from services.planes_service import verificar_limite_asistentes

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hay_otro_admin_activo(gym_id, excluir_id: UUID, db: Session) -> bool:
    """True si existe al menos un admin activo distinto al usuario excluido."""
    return db.query(Usuario).filter(
        Usuario.gym_id == gym_id,
        Usuario.rol    == RolUsuario.admin,
        Usuario.activo == True,
        Usuario.id     != excluir_id,
    ).first() is not None


# ── Schemas ───────────────────────────────────────────────────────────────────

class UsuarioOut(BaseModel):
    id:        UUID
    gym_id:    UUID
    email:     str
    nombre:    str
    rol:       RolUsuario
    activo:    bool
    creado_en: datetime

    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    email:    EmailStr
    password: str
    nombre:   str
    rol:      RolUsuario = RolUsuario.staff

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)

    @field_validator("password")
    @classmethod
    def password_minimo(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return v


class UsuarioUpdate(BaseModel):
    nombre:   Optional[str]        = None
    rol:      Optional[RolUsuario] = None
    activo:   Optional[bool]       = None
    password: Optional[str]        = None

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)

    @field_validator("password")
    @classmethod
    def password_minimo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[UsuarioOut])
def listar_usuarios(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    return (
        db.query(Usuario)
        .filter(Usuario.gym_id == usuario.gym_id)
        .order_by(Usuario.nombre)
        .all()
    )


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obtener_usuario(
    usuario_id: UUID,
    db:         Session       = Depends(get_db_tenant),
    usuario:    UsuarioActual = Depends(require_admin),
):
    u = db.query(Usuario).filter(
        Usuario.id     == usuario_id,
        Usuario.gym_id == usuario.gym_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return u


@router.post("/", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos:   UsuarioCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    if datos.rol == RolUsuario.staff:
        gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
        verificar_limite_asistentes(gimnasio, db)

    nuevo = Usuario(
        gym_id        = usuario.gym_id,
        email         = datos.email,
        password_hash = pwd_context.hash(datos.password),
        nombre        = datos.nombre,
        rol           = datos.rol,
    )
    db.add(nuevo)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email en este gimnasio.",
        ) from e
    db.refresh(nuevo)
    return nuevo


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: UUID,
    datos:      UsuarioUpdate,
    db:         Session       = Depends(get_db_tenant),
    usuario:    UsuarioActual = Depends(require_admin),
):
    u = db.query(Usuario).filter(
        Usuario.id     == usuario_id,
        Usuario.gym_id == usuario.gym_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # Guard: no auto-desactivación vía PATCH (el DELETE ya lo bloquea, el PATCH no tenía guard).
    if datos.activo is False and str(usuario_id) == usuario.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes desactivarte a ti mismo.",
        )

    # Guard: no eliminar el último admin activo (por desactivación o degradación de rol).
    if u.rol == RolUsuario.admin and (datos.activo is False or datos.rol == RolUsuario.staff):
        if not _hay_otro_admin_activo(usuario.gym_id, usuario_id, db):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El gimnasio debe mantener al menos un administrador activo.",
            )

    if datos.nombre is not None:
        u.nombre = datos.nombre
    if datos.rol is not None:
        u.rol = datos.rol
    if datos.activo is not None:
        u.activo = datos.activo
    if datos.password is not None:
        u.password_hash = pwd_context.hash(datos.password)

    db.commit()
    db.refresh(u)
    return u


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_usuario(
    usuario_id: UUID,
    db:         Session       = Depends(get_db_tenant),
    usuario:    UsuarioActual = Depends(require_admin),
):
    if str(usuario_id) == usuario.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes desactivarte a ti mismo.",
        )

    u = db.query(Usuario).filter(
        Usuario.id     == usuario_id,
        Usuario.gym_id == usuario.gym_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if u.rol == RolUsuario.admin and not _hay_otro_admin_activo(usuario.gym_id, usuario_id, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El gimnasio debe mantener al menos un administrador activo.",
        )

    u.activo = False
    db.commit()
