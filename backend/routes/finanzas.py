from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from models import Gasto, Venta, VentaItem, EstadoVenta, Membresia, EstadoMembresia
from auth import require_admin, UsuarioActual, get_db_tenant
from dinero import redondear
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
from security import sanitizar

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class GastoCreate(BaseModel):
    categoria:   str
    descripcion: Optional[str] = None
    monto:       Decimal = Field(gt=0)
    es_fijo:     bool = False

    @field_validator("categoria", "descripcion", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class GastoUpdate(BaseModel):
    categoria:   Optional[str]     = None
    descripcion: Optional[str]     = None
    monto:       Optional[Decimal] = Field(default=None, gt=0)
    es_fijo:     Optional[bool]    = None

    @field_validator("categoria", "descripcion", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# ─── Gastos ──────────────────────────────────────────────────────────────────

@router.get("/gastos")
def listar_gastos(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    return (
        db.query(Gasto)
        .filter(Gasto.gym_id == usuario.gym_id)
        .order_by(Gasto.fecha.desc())
        .all()
    )


@router.post("/gastos", status_code=201)
def crear_gasto(
    data:    GastoCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    gasto = Gasto(
        **data.model_dump(),
        gym_id     = usuario.gym_id,
        creado_por = usuario.user_id,
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


@router.patch("/gastos/{gasto_id}")
def actualizar_gasto(
    gasto_id: int,
    data:     GastoUpdate,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(require_admin),
):
    gasto = db.query(Gasto).filter(
        Gasto.id == gasto_id, Gasto.gym_id == usuario.gym_id,
    ).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado.")
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(gasto, campo, valor)
    db.commit()
    db.refresh(gasto)
    return gasto


@router.delete("/gastos/{gasto_id}", status_code=204)
def eliminar_gasto(
    gasto_id: int,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(require_admin),
):
    gasto = db.query(Gasto).filter(
        Gasto.id == gasto_id, Gasto.gym_id == usuario.gym_id,
    ).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado.")
    db.delete(gasto)
    db.commit()


# ─── Resumen financiero ───────────────────────────────────────────────────────

@router.get("/resumen")
def resumen_financiero(
    mes:     Optional[int] = Query(None, ge=1, le=12),
    anio:    Optional[int] = Query(None, ge=2020),
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    """Resumen mensual: ingresos POS, costos, gastos fijos y variables, ganancia neta."""
    ahora = datetime.now(timezone.utc)
    mes   = mes  or ahora.month
    anio  = anio or ahora.year

    # Ingresos POS: ventas no canceladas del período
    ingresos_ventas = (
        db.query(func.sum(Venta.total))
        .filter(
            Venta.gym_id == usuario.gym_id,
            Venta.estado != EstadoVenta.cancelada,
            extract("month", Venta.creado_en) == mes,
            extract("year",  Venta.creado_en) == anio,
        )
        .scalar() or 0
    )

    # Ingresos por membresías: precio acordado de las membresías vendidas
    # (creadas o renovadas) en el período — misma lógica que ingresos_ventas:
    # se reconoce el valor total del contrato al momento de la venta, no el
    # cobro efectivo (una membresía en abono ya cuenta acá, igual que una
    # venta POS en abono ya cuenta en ingresos_ventas). coalesce cubre el
    # mismo caso borde que precio_acordado_de() en membresia_service.py:
    # precio_acordado es NULL solo en registros previos a la migración 003.
    ingresos_membresias = (
        db.query(func.sum(func.coalesce(Membresia.precio_acordado, Membresia.precio_pagado)))
        .filter(
            Membresia.gym_id == usuario.gym_id,
            Membresia.estado != EstadoMembresia.cancelada,
            extract("month", Membresia.creado_en) == mes,
            extract("year",  Membresia.creado_en) == anio,
        )
        .scalar() or 0
    )

    ingresos = ingresos_ventas + ingresos_membresias

    # Costo de los productos vendidos (del período) — al precio de costo
    # vigente cuando se hizo la venta, no al precio de costo actual
    costo_ventas = (
        db.query(func.sum(VentaItem.cantidad * VentaItem.costo_unitario))
        .join(Venta, VentaItem.venta_id == Venta.id)
        .filter(
            Venta.gym_id == usuario.gym_id,
            Venta.estado != EstadoVenta.cancelada,
            extract("month", Venta.creado_en) == mes,
            extract("year",  Venta.creado_en) == anio,
        )
        .scalar() or 0
    )

    # Gastos variables del período
    gastos_variables = (
        db.query(func.sum(Gasto.monto))
        .filter(
            Gasto.gym_id == usuario.gym_id,
            Gasto.es_fijo == False,
            extract("month", Gasto.fecha) == mes,
            extract("year",  Gasto.fecha) == anio,
        )
        .scalar() or 0
    )

    # Gastos fijos del período (filtrados por mes/año, no histórico total)
    gastos_fijos = (
        db.query(func.sum(Gasto.monto))
        .filter(
            Gasto.gym_id == usuario.gym_id,
            Gasto.es_fijo == True,
            extract("month", Gasto.fecha) == mes,
            extract("year",  Gasto.fecha) == anio,
        )
        .scalar() or 0
    )

    total_gastos   = redondear(gastos_variables + gastos_fijos)
    ganancia_bruta = redondear(ingresos - costo_ventas)
    ganancia_neta  = redondear(ganancia_bruta - total_gastos)

    return {
        "mes":                  mes,
        "anio":                 anio,
        "ingresos":             redondear(ingresos),
        "ingresos_ventas":      redondear(ingresos_ventas),
        "ingresos_membresias":  redondear(ingresos_membresias),
        "costo_ventas":     redondear(costo_ventas),
        "ganancia_bruta":   ganancia_bruta,
        "gastos_fijos":     redondear(gastos_fijos),
        "gastos_variables": redondear(gastos_variables),
        "total_gastos":     total_gastos,
        "ganancia_neta":    ganancia_neta,
    }
