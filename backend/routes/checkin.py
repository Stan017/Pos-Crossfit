from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date, timedelta

from models import Asistencia, Miembro, Membresia, EstadoMembresia, Clase, EstadoClase, Reservacion, EstadoReservacion
from fecha import inicio_dia_ecuador_en_utc
from security import sanitizar
from auth import get_usuario_actual, UsuarioActual, get_db_tenant

_ESTADOS_VIGENTES_CHECKIN = [
    EstadoMembresia.activa,
    EstadoMembresia.por_vencer,
    EstadoMembresia.critica,
    EstadoMembresia.pendiente_pago,
]

router = APIRouter()


class CheckinInput(BaseModel):
    miembro_id: int
    clase_id:   int
    notas:      Optional[str] = None

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


@router.post("/", status_code=status.HTTP_201_CREATED)
def registrar_checkin_y_descontar_clase(
    datos:   CheckinInput,
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    """
    Registra asistencia del miembro.
    Si la membresía activa es por clases, descuenta una clase.
    Si no hay membresía activa, retorna 409.
    """
    miembro = db.query(Miembro).filter(
        Miembro.id     == datos.miembro_id,
        Miembro.gym_id == usuario.gym_id,
        Miembro.activo == True,
    ).first()
    if not miembro:
        raise HTTPException(status_code=404, detail="Miembro no encontrado.")

    # with_for_update() previene race condition cuando dos check-ins concurrentes
    # leen y modifican clases_usadas al mismo tiempo (lost-update)
    membresia = db.query(Membresia).filter(
        Membresia.gym_id     == usuario.gym_id,
        Membresia.miembro_id == datos.miembro_id,
        Membresia.estado.in_(_ESTADOS_VIGENTES_CHECKIN),
    ).with_for_update().first()

    if not membresia:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El miembro no tiene una membresía vigente."
        )

    # Para planes por tiempo: validar que fecha_fin no haya pasado
    # (el campo estado en DB puede estar desactualizado si no se sincronizó)
    if membresia.fecha_fin is not None and membresia.fecha_fin < date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La membresía del miembro ha vencido."
        )

    # Descuenta clase si el plan es por clases
    if membresia.fecha_fin is None:
        if membresia.clases_total is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La membresía no tiene clases configuradas."
            )
        if membresia.clases_usadas >= membresia.clases_total:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El miembro no tiene clases disponibles."
            )
        membresia.clases_usadas += 1
        if membresia.clases_usadas >= membresia.clases_total:
            membresia.estado = EstadoMembresia.vencida

    # with_for_update() por el mismo motivo que reservar_miembro en horarios.py:
    # sin esto, dos check-ins walk-in concurrentes podían contar los mismos
    # cupos disponibles antes de que ninguno confirmara su reserva.
    clase = db.query(Clase).filter(
        Clase.id     == datos.clase_id,
        Clase.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not clase:
        raise HTTPException(status_code=404, detail="Clase no encontrada.")
    if clase.estado == EstadoClase.cancelada:
        raise HTTPException(status_code=409, detail="La clase está cancelada.")

    # Evita doble check-in (retry de red duplicaría el descuento de clase)
    ya_asistio = db.query(Asistencia).filter(
        Asistencia.gym_id     == usuario.gym_id,
        Asistencia.clase_id   == datos.clase_id,
        Asistencia.miembro_id == datos.miembro_id,
    ).first()
    if ya_asistio:
        raise HTTPException(
            status_code=409,
            detail="El miembro ya tiene un check-in registrado para esta clase."
        )

    # Buscar reservación previa; si no existe crearla como walk-in
    reservacion = db.query(Reservacion).filter(
        Reservacion.gym_id     == usuario.gym_id,
        Reservacion.clase_id   == datos.clase_id,
        Reservacion.miembro_id == datos.miembro_id,
    ).first()

    if reservacion is None:
        # Mismo límite que reservar_miembro (horarios.py) — un walk-in sin
        # reserva previa es, para efectos de cupo, una reserva nueva. Sin
        # este chequeo, el check-in directo podía superar clase.capacidad
        # aunque reservar_miembro ya rechazara nuevas reservas por falta de
        # cupo para esa misma clase.
        ocupados = (
            db.query(func.count(Reservacion.id))
            .filter(
                Reservacion.clase_id == datos.clase_id,
                Reservacion.gym_id   == usuario.gym_id,
                Reservacion.estado   == EstadoReservacion.confirmada,
            )
            .scalar()
        )
        if ocupados >= clase.capacidad:
            raise HTTPException(status_code=409, detail="La clase no tiene cupo disponible.")

        reservacion = Reservacion(
            gym_id        = usuario.gym_id,
            clase_id      = datos.clase_id,
            miembro_id    = datos.miembro_id,
            estado        = EstadoReservacion.confirmada,
            canal         = "staff",
            reservado_por = usuario.user_id,
        )
        db.add(reservacion)
        db.flush()

    advertencia = (
        "El miembro tiene un saldo pendiente de pago en su membresía."
        if membresia.estado == EstadoMembresia.pendiente_pago
        else None
    )

    asistencia = Asistencia(
        gym_id         = usuario.gym_id,
        miembro_id     = datos.miembro_id,
        membresia_id   = membresia.id,
        clase_id       = datos.clase_id,
        reservacion_id = reservacion.id,
        notas          = datos.notas,
    )
    db.add(asistencia)
    db.commit()
    db.refresh(asistencia)
    return {
        "id":             asistencia.id,
        "miembro_id":     asistencia.miembro_id,
        "membresia_id":   asistencia.membresia_id,
        "clase_id":       asistencia.clase_id,
        "reservacion_id": asistencia.reservacion_id,
        "fecha":          asistencia.fecha,
        "notas":          asistencia.notas,
        "advertencia":    advertencia,
    }


def _serializar_asistencia(a: Asistencia) -> dict:
    return {
        "id":           a.id,
        "miembro_id":   a.miembro_id,
        "membresia_id": a.membresia_id,
        "clase_id":     a.clase_id,
        "fecha":        a.fecha,
        "notas":        a.notas,
        "miembro": {
            "nombre":   a.miembro.nombre,
            "apellido": a.miembro.apellido,
        } if a.miembro else None,
        "clase": {
            "nombre":      a.clase.nombre,
            "hora_inicio": a.clase.hora_inicio.strftime("%H:%M") if a.clase.hora_inicio else None,
            "entrenador":  a.clase.instructor.nombre if a.clase.instructor else None,
        } if a.clase else None,
    }


@router.get("/")
def listar_asistencias(
    miembro_id:  Optional[int]  = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    db:          Session        = Depends(get_db_tenant),
    usuario:     UsuarioActual  = Depends(get_usuario_actual),
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(
            status_code=422,
            detail="fecha_desde no puede ser posterior a fecha_hasta.",
        )

    query = (
        db.query(Asistencia)
        .options(
            joinedload(Asistencia.miembro),
            joinedload(Asistencia.clase).joinedload(Clase.instructor),
        )
        .filter(Asistencia.gym_id == usuario.gym_id)
    )
    if miembro_id is not None:
        query = query.filter(Asistencia.miembro_id == miembro_id)
    if fecha_desde:
        query = query.filter(Asistencia.fecha >= inicio_dia_ecuador_en_utc(fecha_desde))
    if fecha_hasta:
        query = query.filter(Asistencia.fecha < inicio_dia_ecuador_en_utc(fecha_hasta + timedelta(days=1)))
    return [_serializar_asistencia(a) for a in query.order_by(Asistencia.fecha.desc()).all()]


class NotasInput(BaseModel):
    notas: Optional[str] = None

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


@router.patch("/{asistencia_id}")
def editar_notas_asistencia(
    asistencia_id: int,
    datos:         NotasInput,
    db:            Session        = Depends(get_db_tenant),
    usuario:       UsuarioActual  = Depends(get_usuario_actual),
):
    """
    Corrige/completa la nota de evolución de una asistencia ya registrada.
    En la práctica el terapeuta suele documentar después de terminar la
    sesión, no en el instante del check-in — por eso esto vive separado
    del POST. Sin gating de admin: es documentación clínica de rutina,
    no una acción destructiva (mismo criterio que el POST de check-in).
    """
    asistencia = db.query(Asistencia).filter(
        Asistencia.id     == asistencia_id,
        Asistencia.gym_id == usuario.gym_id,
    ).first()
    if not asistencia:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada.")

    asistencia.notas = datos.notas
    db.commit()
    db.refresh(asistencia)
    return _serializar_asistencia(asistencia)


@router.get("/paciente/{miembro_id}/sesiones")
def listar_sesiones_paciente(
    miembro_id: int,
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    """
    Historial completo de citas de un paciente (asistió / no-show / cancelada /
    pendiente), para la ficha médica en Miembros. A diferencia de GET "/" (que
    solo lista asistencias reales), esto parte de las Reservaciones para poder
    reflejar también las citas a las que el paciente no llegó.
    """
    miembro = db.query(Miembro).filter(
        Miembro.id     == miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).first()
    if not miembro:
        raise HTTPException(status_code=404, detail="Miembro no encontrado.")

    reservaciones = (
        db.query(Reservacion)
        .join(Clase, Reservacion.clase_id == Clase.id)
        .options(joinedload(Reservacion.clase).joinedload(Clase.instructor))
        .filter(
            Reservacion.gym_id     == usuario.gym_id,
            Reservacion.miembro_id == miembro_id,
        )
        .order_by(Clase.fecha.desc(), Clase.hora_inicio.desc())
        .all()
    )

    reservacion_ids = [r.id for r in reservaciones]
    asistencia_por_reservacion = {}
    if reservacion_ids:
        asistencias = db.query(Asistencia).filter(
            Asistencia.gym_id         == usuario.gym_id,
            Asistencia.reservacion_id.in_(reservacion_ids),
        ).all()
        asistencia_por_reservacion = {a.reservacion_id: a for a in asistencias}

    resultado = []
    for r in reservaciones:
        asistencia = asistencia_por_reservacion.get(r.id)
        if r.estado == EstadoReservacion.no_show:
            estado = "no_show"
        elif r.estado == EstadoReservacion.cancelada:
            estado = "cancelada"
        elif asistencia:
            estado = "asistio"
        else:
            estado = "pendiente"
        resultado.append({
            "reservacion_id": r.id,
            "asistencia_id":  asistencia.id if asistencia else None,
            "fecha":          r.clase.fecha if r.clase else None,
            "hora_inicio":    r.clase.hora_inicio.strftime("%H:%M") if r.clase and r.clase.hora_inicio else None,
            "clase_nombre":   r.clase.nombre if r.clase else None,
            "terapeuta":      r.clase.instructor.nombre if r.clase and r.clase.instructor else None,
            "estado":         estado,
            "notas":          asistencia.notas if asistencia else None,
        })
    return resultado
