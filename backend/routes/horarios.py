from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date
from datetime import time as time_type

from models import Clase, Reservacion, Miembro, Asistencia, Instructor, EstadoClase, EstadoReservacion
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from security import sanitizar

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ClaseInput(BaseModel):
    fecha:         date
    hora_inicio:   time_type
    hora_fin:      time_type
    nombre:        str
    instructor_id: Optional[int] = None
    capacidad:     int = Field(default=20, ge=1)
    notas:         Optional[str] = None

    @field_validator("nombre", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)

    @model_validator(mode="after")
    def validar_horario(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")
        return self


class ClaseUpdate(BaseModel):
    fecha:         Optional[date]        = None
    hora_inicio:   Optional[time_type]   = None
    hora_fin:      Optional[time_type]   = None
    nombre:        Optional[str]         = None
    instructor_id: Optional[int]         = None
    capacidad:     Optional[int]         = Field(default=None, ge=1)
    estado:        Optional[EstadoClase] = None
    notas:         Optional[str]         = None

    @field_validator("nombre", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class ReservacionInput(BaseModel):
    miembro_id: int


class ReservacionUpdate(BaseModel):
    estado: EstadoReservacion


# ── Serializers ───────────────────────────────────────────────────────────────

def _serializar_clase(clase: Clase, reservados: int = 0, asistencias: int = 0) -> dict:
    return {
        "id":            clase.id,
        "fecha":         clase.fecha,
        "hora_inicio":   clase.hora_inicio.strftime("%H:%M") if clase.hora_inicio else None,
        "hora_fin":      clase.hora_fin.strftime("%H:%M")    if clase.hora_fin    else None,
        "nombre":        clase.nombre,
        "instructor_id": clase.instructor_id,
        "instructor": {
            "id":     clase.instructor.id,
            "nombre": clase.instructor.nombre,
        } if clase.instructor else None,
        "capacidad":   clase.capacidad,
        "estado":      clase.estado,
        "notas":       clase.notas,
        "creado_en":   clase.creado_en,
        "reservados":  reservados,
        "asistencias": asistencias,
    }


def _validar_instructor(instructor_id: Optional[int], gym_id, db: Session) -> None:
    if instructor_id is None:
        return
    if not db.query(Instructor).filter(
        Instructor.id     == instructor_id,
        Instructor.gym_id == gym_id,
    ).first():
        raise HTTPException(status_code=404, detail="Instructor no encontrado.")


# ── Clases ────────────────────────────────────────────────────────────────────

@router.get("/clases")
def listar_clases(
    fecha:   Optional[date] = Query(None),
    desde:   Optional[date] = Query(None),
    hasta:   Optional[date] = Query(None),
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    query = (
        db.query(Clase)
        .options(joinedload(Clase.instructor))
        .filter(Clase.gym_id == usuario.gym_id)
    )

    if fecha:
        query = query.filter(Clase.fecha == fecha)
    else:
        if desde:
            query = query.filter(Clase.fecha >= desde)
        if hasta:
            query = query.filter(Clase.fecha <= hasta)

    clases = query.order_by(Clase.fecha, Clase.hora_inicio).all()

    clase_ids = [c.id for c in clases]
    counts: dict[int, int] = {}
    asistencia_counts: dict[int, int] = {}
    if clase_ids:
        rows = (
            db.query(Reservacion.clase_id, func.count(Reservacion.id).label("total"))
            .filter(
                Reservacion.gym_id == usuario.gym_id,
                Reservacion.clase_id.in_(clase_ids),
                Reservacion.estado == EstadoReservacion.confirmada,
            )
            .group_by(Reservacion.clase_id)
            .all()
        )
        counts = {r.clase_id: r.total for r in rows}

        filas_asistencia = (
            db.query(Asistencia.clase_id, func.count(Asistencia.id).label("total"))
            .filter(
                Asistencia.gym_id == usuario.gym_id,
                Asistencia.clase_id.in_(clase_ids),
            )
            .group_by(Asistencia.clase_id)
            .all()
        )
        asistencia_counts = {r.clase_id: r.total for r in filas_asistencia}

    return [
        _serializar_clase(c, counts.get(c.id, 0), asistencia_counts.get(c.id, 0))
        for c in clases
    ]


@router.post("/clases", status_code=status.HTTP_201_CREATED)
def crear_clase(
    datos:   ClaseInput,
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    _validar_instructor(datos.instructor_id, usuario.gym_id, db)

    clase = Clase(
        gym_id        = usuario.gym_id,
        fecha         = datos.fecha,
        hora_inicio   = datos.hora_inicio,
        hora_fin      = datos.hora_fin,
        nombre        = datos.nombre,
        instructor_id = datos.instructor_id,
        capacidad     = datos.capacidad,
        notas         = datos.notas,
        creado_por    = usuario.user_id,
    )
    db.add(clase)
    db.commit()
    db.refresh(clase)
    return _serializar_clase(clase)


@router.put("/clases/{clase_id}")
def actualizar_clase(
    clase_id: int,
    datos:    ClaseUpdate,
    db:       Session        = Depends(get_db_tenant),
    usuario:  UsuarioActual  = Depends(get_usuario_actual),
):
    clase = db.query(Clase).filter(
        Clase.id     == clase_id,
        Clase.gym_id == usuario.gym_id,
    ).first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada.")

    datos_dict = datos.model_dump(exclude_unset=True)
    if "instructor_id" in datos_dict:
        _validar_instructor(datos_dict["instructor_id"], usuario.gym_id, db)

    for campo, valor in datos_dict.items():
        setattr(clase, campo, valor)

    # Se valida después de aplicar el PATCH parcial, no antes: si solo viene
    # hora_fin en el body, hora_inicio efectiva es la que ya tenía la fila —
    # eso el schema de ClaseUpdate no lo puede saber por sí solo.
    if clase.hora_fin <= clase.hora_inicio:
        raise HTTPException(
            status_code=422,
            detail="La hora de fin debe ser posterior a la hora de inicio.",
        )

    db.commit()
    db.refresh(clase)
    return _serializar_clase(clase)


@router.patch("/clases/{clase_id}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_clase(
    clase_id: int,
    db:       Session        = Depends(get_db_tenant),
    usuario:  UsuarioActual  = Depends(get_usuario_actual),
):
    clase = db.query(Clase).filter(
        Clase.id     == clase_id,
        Clase.gym_id == usuario.gym_id,
    ).first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada.")

    clase.estado = EstadoClase.cancelada
    db.commit()


@router.delete("/clases/{clase_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_clase(
    clase_id: int,
    db:       Session        = Depends(get_db_tenant),
    usuario:  UsuarioActual  = Depends(get_usuario_actual),
):
    clase = db.query(Clase).filter(
        Clase.id     == clase_id,
        Clase.gym_id == usuario.gym_id,
    ).first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada.")

    total_asistencias = db.query(func.count(Asistencia.id)).filter(
        Asistencia.clase_id == clase_id,
        Asistencia.gym_id   == usuario.gym_id,
    ).scalar()
    if total_asistencias > 0:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: la clase tiene {total_asistencias} "
                   f"asistencia{'s' if total_asistencias != 1 else ''} registrada"
                   f"{'s' if total_asistencias != 1 else ''}. "
                   f"Cancela la clase en vez de eliminarla."
        )

    db.delete(clase)
    db.commit()


# ── Reservaciones ─────────────────────────────────────────────────────────────

@router.get("/clases/{clase_id}/reservaciones")
def listar_reservaciones(
    clase_id: int,
    db:       Session        = Depends(get_db_tenant),
    usuario:  UsuarioActual  = Depends(get_usuario_actual),
):
    clase = db.query(Clase).filter(
        Clase.id     == clase_id,
        Clase.gym_id == usuario.gym_id,
    ).first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada.")

    reservaciones = (
        db.query(Reservacion)
        .options(joinedload(Reservacion.miembro))
        .filter(
            Reservacion.clase_id == clase_id,
            Reservacion.gym_id   == usuario.gym_id,
        )
        .order_by(Reservacion.reservado_en)
        .all()
    )
    return [
        {
            "id":           r.id,
            "miembro_id":   r.miembro_id,
            "estado":       r.estado,
            "canal":        r.canal,
            "reservado_en": r.reservado_en,
            "miembro": {
                "nombre":   r.miembro.nombre,
                "apellido": r.miembro.apellido,
            } if r.miembro else None,
        }
        for r in reservaciones
    ]


@router.post("/clases/{clase_id}/reservaciones", status_code=status.HTTP_201_CREATED)
def reservar_miembro(
    clase_id: int,
    datos:    ReservacionInput,
    db:       Session        = Depends(get_db_tenant),
    usuario:  UsuarioActual  = Depends(get_usuario_actual),
):
    # with_for_update() previene overbooking cuando dos reservas concurrentes
    # cuentan los mismos cupos disponibles antes de que ninguna haya confirmado
    clase = db.query(Clase).filter(
        Clase.id     == clase_id,
        Clase.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada.")
    if clase.estado == EstadoClase.cancelada:
        raise HTTPException(status_code=409, detail="La clase está cancelada.")

    ocupados = (
        db.query(func.count(Reservacion.id))
        .filter(
            Reservacion.clase_id == clase_id,
            Reservacion.gym_id   == usuario.gym_id,
            Reservacion.estado   == EstadoReservacion.confirmada,
        )
        .scalar()
    )
    if ocupados >= clase.capacidad:
        raise HTTPException(status_code=409, detail="La clase no tiene cupo disponible.")

    miembro = db.query(Miembro).filter(
        Miembro.id     == datos.miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).first()
    if not miembro:
        raise HTTPException(status_code=404, detail="Miembro no encontrado.")

    existente = db.query(Reservacion).filter(
        Reservacion.clase_id   == clase_id,
        Reservacion.gym_id     == usuario.gym_id,
        Reservacion.miembro_id == datos.miembro_id,
        Reservacion.estado     == EstadoReservacion.confirmada,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="El miembro ya tiene una reserva para esta clase.")

    reservacion = Reservacion(
        gym_id        = usuario.gym_id,
        clase_id      = clase_id,
        miembro_id    = datos.miembro_id,
        canal         = "staff",
        reservado_por = usuario.user_id,
    )
    db.add(reservacion)
    db.commit()
    db.refresh(reservacion)
    return {
        "id":         reservacion.id,
        "clase_id":   reservacion.clase_id,
        "miembro_id": reservacion.miembro_id,
        "estado":     reservacion.estado,
        "canal":      reservacion.canal,
        "miembro": {
            "nombre":   miembro.nombre,
            "apellido": miembro.apellido,
        },
    }


@router.put("/reservaciones/{reservacion_id}")
def actualizar_reservacion(
    reservacion_id: int,
    datos:          ReservacionUpdate,
    db:             Session        = Depends(get_db_tenant),
    usuario:        UsuarioActual  = Depends(get_usuario_actual),
):
    reservacion = db.query(Reservacion).filter(
        Reservacion.id     == reservacion_id,
        Reservacion.gym_id == usuario.gym_id,
    ).first()
    if not reservacion:
        raise HTTPException(status_code=404, detail="Reservación no encontrada.")

    reservacion.estado = datos.estado
    db.commit()
    return {"id": reservacion.id, "estado": reservacion.estado}
