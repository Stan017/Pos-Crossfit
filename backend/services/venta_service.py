"""
Cálculo de IVA/total y de estado (pagada/abono) de una Venta.

Centralizado acá porque routes/ventas.py necesita este mismo cálculo en tres
lugares distintos — crear_venta_y_descontar_stock, reemplazar_items_y_
recalcular_stock y agregar_costo_extra_y_recalcular_totales — cada uno
recalcula subtotal/monto_iva/total y decide el estado resultante. Antes de
esto estaba reimplementado a mano en los tres, con el riesgo real de que un
cambio en la fórmula (ej. redondeo, orden de operaciones) se actualizara en
dos de los tres lugares y no en el tercero.
"""
from decimal import Decimal

from models import EstadoVenta
from dinero import a_decimal, redondear


def calcular_montos(subtotal: Decimal, porcentaje_iva) -> tuple[Decimal, Decimal]:
    """A partir del subtotal y el % de IVA, devuelve (monto_iva, total), redondeados."""
    monto_iva = redondear(a_decimal(subtotal) * a_decimal(porcentaje_iva) / 100)
    total     = redondear(a_decimal(subtotal) + monto_iva)
    return monto_iva, total


def calcular_estado_venta(total_pagado, total) -> EstadoVenta:
    """pagada si lo pagado cubre el total, abono si queda saldo pendiente."""
    return EstadoVenta.pagada if a_decimal(total_pagado) >= a_decimal(total) else EstadoVenta.abono
