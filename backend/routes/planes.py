from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session
from typing import Optional
from decimal import Decimal

from models import Plan, Membresia, TipoPlan, EstadoMembresia
from auth import get_usuario_actual, require_admin, UsuarioActual, get_db_tenant
from dinero import a_decimal
from services.membresia_service import calcular_estado, batch_saldos

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PlanCreate(BaseModel):
    nombre:        str
    tipo:          TipoPlan
    duracion_dias: Optional[int]   = None  # requerido si tipo='tiempo'
    clases_total:  Optional[int]   = None  # requerido si tipo='clases'
    precio:        Decimal

    @model_validator(mode="after")
    def validar_campos_por_tipo(self):
        if self.tipo == TipoPlan.tiempo:
            if not self.duracion_dias or self.duracion_dias <= 0:
                raise ValueError("duracion_dias es requerido y debe ser > 0 para planes por tiempo.")
            if self.clases_total is not None:
                raise ValueError("clases_total no aplica para planes por tiempo.")
        else:
            if not self.clases_total or self.clases_total <= 0:
                raise ValueError("clases_total es requerido y debe ser > 0 para planes por clases.")
            if self.duracion_dias is not None:
                raise ValueError("duracion_dias no aplica para planes por clases.")
        return self


class PlanUpdate(BaseModel):
    nombre:        Optional[str]     = None
    precio:        Optional[Decimal] = None
    duracion_dias: Optional[int]     = None
    clases_total:  Optional[int]     = None

    @model_validator(mode="after")
    def validar_valores_positivos(self):
        if self.duracion_dias is not None and self.duracion_dias <= 0:
            raise ValueError("duracion_dias debe ser > 0.")
        if self.clases_total is not None and self.clases_total <= 0:
            raise ValueError("clases_total debe ser > 0.")
        if self.precio is not None and self.precio < 0:
            raise ValueError("precio no puede ser negativo.")
        return self


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def listar_planes(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Lista todos los planes activos del gimnasio."""
    return (
        db.query(Plan)
        .filter(Plan.gym_id == usuario.gym_id, Plan.activo == True)
        .order_by(Plan.tipo, Plan.precio)
        .all()
    )


@router.get("/todos")
def listar_planes_todos(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    """Lista todos los planes del gimnasio incluyendo inactivos (admin)."""
    return (
        db.query(Plan)
        .filter(Plan.gym_id == usuario.gym_id)
        .order_by(Plan.activo.desc(), Plan.tipo, Plan.precio)
        .all()
    )


@router.get("/{plan_id}")
def obtener_plan(
    plan_id: int,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    plan = db.query(Plan).filter(
        Plan.id     == plan_id,
        Plan.gym_id == usuario.gym_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    return plan


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_plan(
    datos:   PlanCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    plan = Plan(
        gym_id        = usuario.gym_id,
        nombre        = datos.nombre,
        tipo          = datos.tipo,
        duracion_dias = datos.duracion_dias,
        clases_total  = datos.clases_total,
        precio        = datos.precio,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}")
def actualizar_plan(
    plan_id: int,
    datos:   PlanUpdate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    """
    Actualiza nombre, precio, duracion_dias o clases_total.
    El campo tipo no es modificable — crea un plan nuevo si necesitas cambiar el tipo.
    """
    plan = db.query(Plan).filter(
        Plan.id     == plan_id,
        Plan.gym_id == usuario.gym_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")

    if datos.duracion_dias is not None and plan.tipo != TipoPlan.tiempo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="duracion_dias solo aplica a planes por tiempo.",
        )
    if datos.clases_total is not None and plan.tipo != TipoPlan.clases:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="clases_total solo aplica a planes por clases.",
        )

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(plan, campo, valor)

    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_plan(
    plan_id: int,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    """
    Desactiva un plan (soft delete).
    Las membresías existentes que usan este plan no se ven afectadas.
    El plan deja de aparecer en el listado de planes disponibles.
    """
    plan = db.query(Plan).filter(
        Plan.id     == plan_id,
        Plan.gym_id == usuario.gym_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")

    # Membresia.estado solo se re-sincroniza en escrituras (crear/renovar/
    # pagar) — una membresía marcada "activa" en DB puede ya haber vencido
    # sin que nadie la tocara, y bloquearía desactivar el plan sin motivo
    # real. Filtrar por estado=="activa" acá no arriesga falsos negativos
    # (nada pasa de "vencida" a "activa" sin una escritura que ya resincroniza),
    # así que alcanza con recalcular las candidatas que ya son "activa" en DB.
    _candidatas = db.query(Membresia).filter(
        Membresia.gym_id  == usuario.gym_id,
        Membresia.plan_id == plan_id,
        Membresia.estado  == EstadoMembresia.activa,
    ).all()
    _saldos = batch_saldos(_candidatas, db)
    membresias_activas = sum(
        1 for m in _candidatas
        if calcular_estado(m, _saldos.get(m.id, a_decimal(0))) == EstadoMembresia.activa
    )

    if membresias_activas > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El plan tiene {membresias_activas} membresía(s) activa(s). "
                   "Espera a que venzan o cancélalas antes de desactivar el plan.",
        )

    plan.activo = False
    db.commit()
