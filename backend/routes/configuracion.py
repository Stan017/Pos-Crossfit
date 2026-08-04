from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Gimnasio
from auth import get_usuario_actual, require_admin, UsuarioActual, get_db_tenant
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from security import sanitizar

router = APIRouter()


class ConfiguracionUpdate(BaseModel):
    nombre:      Optional[str]   = None
    ruc:         Optional[str]   = None
    telefono:    Optional[str]   = None
    direccion:   Optional[str]   = None
    iva_default: Optional[float] = Field(default=None, ge=0)

    @field_validator("nombre", "ruc", "telefono", "direccion", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


@router.get("/")
def obtener_configuracion(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")
    return {
        "nombre":      gimnasio.nombre,
        "email":       gimnasio.email,
        "ruc":         gimnasio.ruc,
        "telefono":    gimnasio.telefono,
        "direccion":   gimnasio.direccion,
        "pais":        gimnasio.pais,
        "iva_default": gimnasio.iva_default,
        "logo_url":    gimnasio.logo_url,
    }


@router.patch("/")
def actualizar_configuracion(
    data:    ConfiguracionUpdate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")

    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(gimnasio, campo, valor)

    db.commit()
    db.refresh(gimnasio)
    return {
        "nombre":      gimnasio.nombre,
        "email":       gimnasio.email,
        "ruc":         gimnasio.ruc,
        "telefono":    gimnasio.telefono,
        "direccion":   gimnasio.direccion,
        "pais":        gimnasio.pais,
        "iva_default": gimnasio.iva_default,
    }
