"""
Lógica de negocio del estado real de una membresía
(activa / por_vencer / critica / vencida / pendiente_pago / cancelada).

Centralizado acá y no en routes/membresias.py: dashboard.py, deudas.py y
planes.py también necesitan saber el estado REAL de una membresía para
reportes y validaciones — no solo las rutas de escritura de membresias.py.

La columna Membresia.estado persistida solo se actualiza en escrituras
(crear/renovar/pagar). Cualquier lectura que filtre por esa columna en vez
de recalcular con calcular_estado() queda desactualizada apenas pasa el
tiempo sin que nadie toque la fila — el caso más claro es una membresía por
tiempo que vence sin que nadie la renueve ni pague: nada la marca "vencida"
en DB hasta la próxima escritura, que puede no llegar nunca.
"""
from decimal import Decimal
from datetime import date

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from models import Membresia, PagoMembresia, EstadoMembresia
from dinero import a_decimal, redondear

DIAS_CRITICO    = 2
DIAS_POR_VENCER = 7

# Estados que indican membresía en uso (no vencida ni cancelada)
ESTADOS_VIGENTES = {
    EstadoMembresia.activa,
    EstadoMembresia.por_vencer,
    EstadoMembresia.critica,
    EstadoMembresia.pendiente_pago,
}


def precio_acordado_de(membresia: Membresia) -> Decimal:
    """
    Precio real acordado de una membresía. precio_acordado es NULL solo en
    registros previos a la migración 003 (antes de que la columna existiera)
    — en ese caso se cae a precio_pagado. Explícito con "is not None", no con
    `or`: un precio_acordado en 0 (membresía comped/gratis) es un valor real
    y "or" lo trataría igual que None, cayendo al precio_pagado incorrecto.
    """
    if membresia.precio_acordado is not None:
        return a_decimal(membresia.precio_acordado)
    if membresia.precio_pagado is not None:
        return a_decimal(membresia.precio_pagado)
    return a_decimal(0)


def calcular_estado(membresia: Membresia, saldo: float = 0.0) -> EstadoMembresia:
    """
    Calcula el estado real de una membresía en runtime.
    saldo: precio_acordado - total pagado. Si > 0, la membresía tiene deuda pendiente.
    Regla de prioridad: vencida > pendiente_pago > critica > por_vencer > activa
    """
    # cancelada y vencida son estados terminales que un caller fijó a
    # propósito (staff cancela, o renovar_membresia/crear_membresia marcan la
    # fila vieja al reemplazarla) — no algo que recalcular desde fecha_fin.
    # Sin este corte, una membresía renovada ANTES de llegar a su fecha_fin
    # real volvía a mostrar "activa" acá (fecha_fin todavía no pasó), aunque
    # ya estuviera reemplazada por la nueva — encontrado escribiendo el test
    # de renovar_membresia. No hay riesgo de "vencida" quedar stale al revés:
    # una membresía que vence sola (sin que nadie la toque) nunca tiene
    # "vencida" en la columna todavía — por eso esta función existe, para
    # recalcularla fresca en ese caso — así que este corte solo interviene
    # cuando alguien la marcó vencida a mano, que es justo la intención.
    if membresia.estado in (EstadoMembresia.cancelada, EstadoMembresia.vencida):
        return membresia.estado

    hoy = date.today()

    # ── Plan por clases ────────────────────────────────────────────────────────
    if membresia.fecha_fin is None:
        if membresia.clases_total is None:
            return EstadoMembresia.cancelada  # dato corrupto
        if membresia.clases_usadas >= membresia.clases_total:
            return EstadoMembresia.vencida
        if saldo > 0:
            return EstadoMembresia.pendiente_pago
        if membresia.clases_usadas >= membresia.clases_total - DIAS_CRITICO:
            return EstadoMembresia.critica
        return EstadoMembresia.activa

    # ── Plan por tiempo ────────────────────────────────────────────────────────
    if membresia.fecha_fin < hoy:
        return EstadoMembresia.vencida  # vencida gana aunque haya deuda
    if saldo > 0:
        return EstadoMembresia.pendiente_pago
    dias = (membresia.fecha_fin - hoy).days
    if dias <= DIAS_CRITICO:
        return EstadoMembresia.critica
    if dias <= DIAS_POR_VENCER:
        return EstadoMembresia.por_vencer
    return EstadoMembresia.activa


def calcular_saldo(membresia: Membresia, db: Session) -> Decimal:
    """Saldo pendiente = precio_acordado - suma de todos los pagos registrados."""
    precio_acordado = precio_acordado_de(membresia)
    total_pagado = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(PagoMembresia.monto), 0))
        .filter(
            PagoMembresia.gym_id       == membresia.gym_id,
            PagoMembresia.membresia_id == membresia.id,
        )
        .scalar()
    )
    return redondear(max(a_decimal(0), precio_acordado - a_decimal(total_pagado)))


def batch_saldos(membresias: list[Membresia], db: Session) -> dict[int, Decimal]:
    """Calcula saldos para una lista de membresías en una sola query."""
    if not membresias:
        return {}
    ids    = [m.id for m in membresias]
    gym_id = membresias[0].gym_id
    rows = (
        db.query(PagoMembresia.membresia_id, sqlfunc.sum(PagoMembresia.monto))
        .filter(
            PagoMembresia.gym_id         == gym_id,
            PagoMembresia.membresia_id.in_(ids),
        )
        .group_by(PagoMembresia.membresia_id)
        .all()
    )
    total_pagados = {row[0]: a_decimal(row[1]) for row in rows}
    result = {}
    for m in membresias:
        precio = precio_acordado_de(m)
        result[m.id] = redondear(max(a_decimal(0), precio - total_pagados.get(m.id, a_decimal(0))))
    return result
