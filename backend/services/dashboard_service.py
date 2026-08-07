"""
KPIs del dashboard del gym (membresías activas, alertas, revenue, deuda,
top productos). Antes vivía entero en routes/dashboard.py — se mueve acá
por el mismo criterio que el resto de services/: la ruta valida input y
llama, esto hace las queries y el cálculo.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from models import (
    Venta, VentaItem, Producto, Miembro, Membresia, Asistencia,
    EstadoVenta, EstadoMembresia, Pago,
)
from dinero import a_decimal, redondear
from services.membresia_service import calcular_estado, batch_saldos, ESTADOS_VIGENTES


def calcular_kpis(
    db: Session, gym_id: UUID, mes_actual: int, anio_actual: int, es_admin: bool
) -> dict:
    hoy = date.today()
    limite_alerta = hoy + timedelta(days=7)

    # Membresías vigentes: activa + por_vencer + critica + pendiente_pago.
    # No se filtra por la columna Membresia.estado directamente: esa columna
    # solo se actualiza en escrituras (crear/renovar/pagar) — una membresía
    # que venció sin que nadie la tocara sigue contando como "activa" en DB.
    # Se recalcula el estado real de cada una, igual que listar_membresias().
    _candidatas = (
        db.query(Membresia)
        .filter(
            Membresia.gym_id == gym_id,
            Membresia.estado != EstadoMembresia.cancelada,
        )
        .all()
    )
    _saldos_candidatas = batch_saldos(_candidatas, db)
    membresias_activas = sum(
        1 for m in _candidatas
        if calcular_estado(m, _saldos_candidatas.get(m.id, a_decimal(0))) in ESTADOS_VIGENTES
    )

    # Alertas: membresías por tiempo que vencen en ≤7 días (no canceladas)
    alertas_tiempo = (
        db.query(func.count(Membresia.id))
        .filter(
            Membresia.gym_id    == gym_id,
            Membresia.estado    != EstadoMembresia.cancelada,
            Membresia.fecha_fin != None,
            Membresia.fecha_fin >= hoy,
            Membresia.fecha_fin <= limite_alerta,
        )
        .scalar() or 0
    )

    # Alertas: planes por clases con ≤2 clases disponibles
    # Los guards != None evitan que NULL - 0 <= 2 evalúe a NULL en PostgreSQL
    alertas_clases = (
        db.query(func.count(Membresia.id))
        .filter(
            Membresia.gym_id       == gym_id,
            Membresia.estado       == EstadoMembresia.activa,
            Membresia.fecha_fin    == None,
            Membresia.clases_total != None,
            Membresia.clases_usadas != None,
            Membresia.clases_total - Membresia.clases_usadas <= 2,
        )
        .scalar() or 0
    )

    # Revenue del mes: solo para admin (datos financieros)
    revenue_mes:      Optional[Decimal] = None
    ventas_mes_count: Optional[int]     = None
    if es_admin:
        revenue_ventas = a_decimal(
            db.query(func.sum(Venta.total))
            .filter(
                Venta.gym_id == gym_id,
                Venta.estado != EstadoVenta.cancelada,
                extract("month", Venta.creado_en) == mes_actual,
                extract("year",  Venta.creado_en) == anio_actual,
            )
            .scalar() or 0
        )
        # Mismo criterio que ingresos_membresias en finanzas.py: se reconoce
        # el precio acordado de la membresía al momento de la venta (creado_en),
        # no el cobro efectivo — igual que Venta.total ya cuenta una venta en
        # abono completa, no solo lo pagado hasta ahora.
        revenue_membresias = a_decimal(
            db.query(func.sum(func.coalesce(Membresia.precio_acordado, Membresia.precio_pagado)))
            .filter(
                Membresia.gym_id == gym_id,
                Membresia.estado != EstadoMembresia.cancelada,
                extract("month", Membresia.creado_en) == mes_actual,
                extract("year",  Membresia.creado_en) == anio_actual,
            )
            .scalar() or 0
        )
        revenue_mes = redondear(revenue_ventas + revenue_membresias)
        ventas_mes_count = (
            db.query(func.count(Venta.id))
            .filter(
                Venta.gym_id == gym_id,
                Venta.estado != EstadoVenta.cancelada,
                extract("month", Venta.creado_en) == mes_actual,
                extract("year",  Venta.creado_en) == anio_actual,
            )
            .scalar() or 0
        )

    # Miembros nuevos del mes (según fecha_ingreso, no creado_en: es la fecha
    # de negocio que el staff carga, no el timestamp técnico del registro)
    nuevos_mes = (
        db.query(func.count(Miembro.id))
        .filter(
            Miembro.gym_id == gym_id,
            extract("month", Miembro.fecha_ingreso) == mes_actual,
            extract("year",  Miembro.fecha_ingreso) == anio_actual,
        )
        .scalar() or 0
    )

    # Asistencias de hoy
    asistencias_hoy = (
        db.query(func.count(Asistencia.id))
        .filter(
            Asistencia.gym_id == gym_id,
            func.date(Asistencia.fecha) == hoy,
        )
        .scalar() or 0
    )

    # Productos con stock bajo (stock <= stock_minimo)
    stock_bajo = (
        db.query(func.count(Producto.id))
        .filter(
            Producto.gym_id == gym_id,
            Producto.activo == True,
            Producto.stock  <= Producto.stock_minimo,
        )
        .scalar() or 0
    )

    # Deuda total: saldo pendiente de ventas POS en abono + membresías con deuda real.
    _total_ventas_abono = a_decimal(
        db.query(func.coalesce(func.sum(Venta.total), 0))
        .filter(Venta.gym_id == gym_id, Venta.estado == EstadoVenta.abono)
        .scalar()
    )
    _pagado_ventas_abono = a_decimal(
        db.query(func.coalesce(func.sum(Pago.monto), 0))
        .join(Venta, Pago.venta_id == Venta.id)
        .filter(Venta.gym_id == gym_id, Venta.estado == EstadoVenta.abono)
        .scalar()
    )

    # Igual que listar_deudas() en deudas.py: no se filtra por la columna
    # Membresia.estado directamente (solo se sincroniza en escrituras). Se
    # reutilizan _candidatas/_saldos_candidatas ya calculados arriba para
    # membresias_activas — de lo contrario este KPI podía mostrar MENOS deuda
    # que /deudas para el mismo gimnasio, porque una membresía vencida con
    # saldo pendiente deja de tener estado "pendiente_pago" en DB apenas se
    # recalcula, y antes desaparecía de este total sin desaparecer de /deudas.
    deuda_membresias = a_decimal(0)
    for m in _candidatas:
        saldo_m = _saldos_candidatas.get(m.id, a_decimal(0))
        if saldo_m <= 0:
            continue
        if calcular_estado(m, saldo_m) in (EstadoMembresia.pendiente_pago, EstadoMembresia.vencida):
            deuda_membresias += saldo_m

    deuda_total = redondear(
        max(a_decimal(0), _total_ventas_abono - _pagado_ventas_abono) +
        deuda_membresias
    )

    # Top 5 productos del mes: solo para admin
    top_productos = []
    if es_admin:
        top_productos = (
            db.query(
                Producto.nombre,
                Producto.categoria,
                func.sum(VentaItem.cantidad).label("unidades_vendidas"),
                func.sum(VentaItem.subtotal).label("total_vendido"),
            )
            .join(VentaItem, Producto.id == VentaItem.producto_id)
            .join(Venta, VentaItem.venta_id == Venta.id)
            .filter(
                Producto.gym_id == gym_id,
                Venta.estado    != EstadoVenta.cancelada,
                extract("month", Venta.creado_en) == mes_actual,
                extract("year",  Venta.creado_en) == anio_actual,
            )
            .group_by(Producto.id, Producto.nombre, Producto.categoria)
            .order_by(func.sum(VentaItem.cantidad).desc())
            .limit(5)
            .all()
        )

    return {
        "mes":                mes_actual,
        "anio":               anio_actual,
        "membresias_activas": membresias_activas,
        "nuevos_mes":         nuevos_mes,
        "alertas":            alertas_tiempo + alertas_clases,
        "revenue_mes":        revenue_mes,
        "ventas_mes":         ventas_mes_count,
        "asistencias_hoy":    asistencias_hoy,
        "stock_bajo":         stock_bajo,
        "deuda_total":        deuda_total,
        "top_productos": [
            {
                "nombre":            r.nombre,
                "categoria":         r.categoria,
                "unidades_vendidas": r.unidades_vendidas,
                "total_vendido":     redondear(r.total_vendido),
            }
            for r in top_productos
        ],
    }
