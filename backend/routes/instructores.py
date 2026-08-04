from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from typing import Optional

from models import Instructor, Clase, Asistencia, Gimnasio, TipoInstructor
from auth import get_usuario_actual, require_admin, UsuarioActual, get_db_tenant
from security import sanitizar
from fecha import inicio_mes_ecuador_en_utc, primer_dia_mes_siguiente
from services.planes_service import verificar_limite_medicos

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class InstructorCreate(BaseModel):
    nombre:   str
    telefono: Optional[str] = None
    tipo:     TipoInstructor

    @field_validator("nombre", "telefono", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class InstructorUpdate(BaseModel):
    nombre:   Optional[str]           = None
    telefono: Optional[str]           = None
    tipo:     Optional[TipoInstructor] = None
    activo:   Optional[bool]          = None

    @field_validator("nombre", "telefono", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def listar_instructores(
    activo:  Optional[bool] = Query(None),
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    query = db.query(Instructor).filter(Instructor.gym_id == usuario.gym_id)
    if activo is not None:
        query = query.filter(Instructor.activo == activo)
    return query.order_by(Instructor.activo.desc(), Instructor.nombre).all()


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_instructor(
    datos:   InstructorCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    verificar_limite_medicos(gimnasio, db)

    instructor = Instructor(
        gym_id     = usuario.gym_id,
        nombre     = datos.nombre,
        telefono   = datos.telefono,
        tipo       = datos.tipo,
        creado_por = usuario.user_id,
    )
    db.add(instructor)
    db.commit()
    db.refresh(instructor)
    return instructor


@router.patch("/{instructor_id}")
def actualizar_instructor(
    instructor_id: int,
    datos:         InstructorUpdate,
    db:            Session       = Depends(get_db_tenant),
    usuario:       UsuarioActual = Depends(require_admin),
):
    instructor = db.query(Instructor).filter(
        Instructor.id     == instructor_id,
        Instructor.gym_id == usuario.gym_id,
    ).first()
    if not instructor:
        raise HTTPException(status_code=404, detail="Instructor no encontrado.")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(instructor, campo, valor)

    db.commit()
    db.refresh(instructor)
    return instructor


@router.patch("/{instructor_id}/desactivar", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_instructor(
    instructor_id: int,
    db:            Session       = Depends(get_db_tenant),
    usuario:       UsuarioActual = Depends(require_admin),
):
    """
    Desactiva un instructor (soft delete). Las clases ya asignadas a este
    instructor no se ven afectadas — solo deja de aparecer como opción al
    programar clases nuevas. Para instructores con historial real de
    clientes, esta es la única opción (ver eliminar_instructor).
    """
    instructor = db.query(Instructor).filter(
        Instructor.id     == instructor_id,
        Instructor.gym_id == usuario.gym_id,
    ).first()
    if not instructor:
        raise HTTPException(status_code=404, detail="Instructor no encontrado.")

    instructor.activo = False
    db.commit()


@router.delete("/{instructor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_instructor(
    instructor_id: int,
    db:            Session       = Depends(get_db_tenant),
    usuario:       UsuarioActual = Depends(require_admin),
):
    """
    Elimina un instructor definitivamente — solo si nunca atendió clientes.
    Mismo criterio que cancelar vs. eliminar una clase (horarios.py): un
    borrado real solo procede si no hay historia real detrás; si la hay, la
    única opción es desactivar (arriba).
    """
    instructor = db.query(Instructor).filter(
        Instructor.id     == instructor_id,
        Instructor.gym_id == usuario.gym_id,
    ).first()
    if not instructor:
        raise HTTPException(status_code=404, detail="Instructor no encontrado.")

    # creado_por es UUID en la columna pero usuario.user_id es el string del
    # claim "sub" del JWT — comparar directo (UUID == str) siempre da False
    # en Python aunque sean "el mismo" id, a diferencia de un filtro SQL
    # donde el driver castea. Por eso el str() explícito de los dos lados.
    # None = instructor del backfill de la 013, sin dueño real: no se restringe.
    if instructor.creado_por is not None and str(instructor.creado_por) != str(usuario.user_id):
        raise HTTPException(
            status_code=403,
            detail="Solo el admin que creó este instructor puede eliminarlo. Podés desactivarlo en su lugar.",
        )

    total_clientes = (
        db.query(func.count(func.distinct(Asistencia.miembro_id)))
        .join(Clase, Clase.id == Asistencia.clase_id)
        .filter(
            Clase.instructor_id == instructor_id,
            Clase.gym_id        == usuario.gym_id,
            Asistencia.gym_id   == usuario.gym_id,
        )
        .scalar()
    )
    if total_clientes > 0:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: tiene {total_clientes} "
                   f"cliente{'s' if total_clientes != 1 else ''} asignado"
                   f"{'s' if total_clientes != 1 else ''}. Desactívalo en vez de eliminarlo.",
        )

    db.delete(instructor)
    db.commit()


@router.get("/reporte")
def reporte_clientes_por_instructor(
    mes:     int            = Query(..., ge=1, le=12),
    anio:    int            = Query(..., ge=2020),
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    """
    Cuántos clientes distintos asistió cada instructor activo en un mes dado
    (clientes distintos, no clases dictadas — un mismo miembro que fue 8
    veces con el mismo instructor cuenta una sola vez).

    El filtro de fecha va en la condición del JOIN, no en el WHERE: si fuera
    un WHERE, un instructor sin ninguna asistencia en el mes (LEFT JOIN trae
    NULL) quedaría excluido igual que si fuera un INNER JOIN, y desaparecería
    del reporte en vez de mostrar 0.
    """
    desde_utc = inicio_mes_ecuador_en_utc(anio, mes)
    siguiente = primer_dia_mes_siguiente(anio, mes)
    hasta_utc = inicio_mes_ecuador_en_utc(siguiente.year, siguiente.month)

    filas = (
        db.query(
            Instructor.id,
            Instructor.nombre,
            func.count(func.distinct(Asistencia.miembro_id)).label("clientes"),
        )
        .outerjoin(Clase, and_(
            Clase.instructor_id == Instructor.id,
            Clase.gym_id        == Instructor.gym_id,
        ))
        .outerjoin(Asistencia, and_(
            Asistencia.clase_id == Clase.id,
            Asistencia.fecha    >= desde_utc,
            Asistencia.fecha    <  hasta_utc,
        ))
        .filter(
            Instructor.gym_id == usuario.gym_id,
            Instructor.activo == True,
        )
        .group_by(Instructor.id, Instructor.nombre)
        .order_by(Instructor.nombre)
        .all()
    )

    return {
        "mes":  mes,
        "anio": anio,
        "instructores": [
            {"instructor_id": f.id, "nombre": f.nombre, "clientes": f.clientes}
            for f in filas
        ],
    }
