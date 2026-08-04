from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from models import HistorialMedico, TipoHistorialMedico, Miembro
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from security import sanitizar

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class HistorialMedicoCreate(BaseModel):
    paciente_id: int
    tipo:        TipoHistorialMedico
    descripcion: str
    fecha:       Optional[date] = None
    activa:      bool = True
    notas:       Optional[str] = None

    @field_validator("descripcion", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class HistorialMedicoUpdate(BaseModel):
    # tipo NO es editable: si se cargó mal la categoría, se borra y se
    # recrea, no se reclasifica un registro existente.
    descripcion: Optional[str]  = None
    fecha:       Optional[date] = None
    activa:      Optional[bool] = None
    notas:       Optional[str]  = None

    @field_validator("descripcion", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/miembro/{miembro_id}")
def listar_historial_medico(
    miembro_id: int,
    db:         Session       = Depends(get_db_tenant),
    usuario:    UsuarioActual = Depends(get_usuario_actual),
):
    if not db.query(Miembro).filter(
        Miembro.id     == miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).first():
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    return (
        db.query(HistorialMedico)
        .filter(
            HistorialMedico.gym_id      == usuario.gym_id,
            HistorialMedico.paciente_id == miembro_id,
        )
        .order_by(HistorialMedico.fecha.desc().nullslast(), HistorialMedico.creado_en.desc())
        .all()
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_historial_medico(
    datos:   HistorialMedicoCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    if not db.query(Miembro).filter(
        Miembro.id     == datos.paciente_id,
        Miembro.gym_id == usuario.gym_id,
    ).first():
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    registro = HistorialMedico(
        gym_id      = usuario.gym_id,
        paciente_id = datos.paciente_id,
        tipo        = datos.tipo,
        descripcion = datos.descripcion,
        fecha       = datos.fecha,
        activa      = datos.activa,
        notas       = datos.notas,
        creado_por  = usuario.user_id,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.patch("/{registro_id}")
def actualizar_historial_medico(
    registro_id: int,
    datos:       HistorialMedicoUpdate,
    db:          Session       = Depends(get_db_tenant),
    usuario:     UsuarioActual = Depends(get_usuario_actual),
):
    registro = db.query(HistorialMedico).filter(
        HistorialMedico.id     == registro_id,
        HistorialMedico.gym_id == usuario.gym_id,
    ).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(registro, campo, valor)

    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{registro_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_historial_medico(
    registro_id: int,
    db:          Session       = Depends(get_db_tenant),
    usuario:     UsuarioActual = Depends(get_usuario_actual),
):
    """
    Elimina un registro definitivamente — restringido a quien lo creó, mismo
    criterio que eliminar_instructor en routes/instructores.py. Acá no hay
    caso de creado_por NULL (a diferencia de Instructor, que tiene backfill
    histórico): esta tabla es nueva, todo registro tiene un dueño real.
    """
    registro = db.query(HistorialMedico).filter(
        HistorialMedico.id     == registro_id,
        HistorialMedico.gym_id == usuario.gym_id,
    ).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")

    if str(registro.creado_por) != str(usuario.user_id):
        raise HTTPException(
            status_code=403,
            detail="Solo el usuario que creó este registro puede eliminarlo.",
        )

    db.delete(registro)
    db.commit()
