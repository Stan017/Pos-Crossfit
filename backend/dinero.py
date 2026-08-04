"""
Helpers de aritmética de dinero exacta con Decimal.

Nunca usar Decimal(valor) directo sobre un float — preserva el error de
representación binaria (Decimal(45.99) da Decimal('45.9899999999999949...')).
Siempre pasar por str() primero.
"""
from decimal import Decimal, ROUND_HALF_UP

DOS_DECIMALES = Decimal('0.01')


def a_decimal(valor) -> Decimal:
    """Convierte un float/int/str/Decimal a Decimal exacto."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def redondear(valor) -> Decimal:
    """Redondea a 2 decimales. Reemplazo de round(x, 2) para Decimal."""
    return a_decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
