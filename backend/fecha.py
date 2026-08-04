"""
Conversión de fechas de calendario Ecuador (UTC-5 fijo, sin horario de
verano) a límites UTC para filtrar columnas timestamptz.

Comparar un timestamptz contra un `date` suelto lo interpreta en UTC, no en
hora de Ecuador — un evento de las 11pm local ya cae del lado de "mañana" en
UTC. Centralizado acá porque más de una ruta necesita el mismo ajuste
(checkin.py filtra por día, instructores.py por mes).
"""
from datetime import date, datetime, time, timedelta, timezone

ECUADOR_UTC_OFFSET_HORAS = 5


def inicio_dia_ecuador_en_utc(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc) + timedelta(hours=ECUADOR_UTC_OFFSET_HORAS)


def inicio_mes_ecuador_en_utc(anio: int, mes: int) -> datetime:
    """Instante UTC que corresponde al día 1 del mes, medianoche hora Ecuador."""
    return inicio_dia_ecuador_en_utc(date(anio, mes, 1))


def primer_dia_mes_siguiente(anio: int, mes: int) -> date:
    return date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)


def es_dia_habil(d: date) -> bool:
    """Lunes a sábado cuentan como hábiles acá — solo domingo no."""
    return d.weekday() != 6  # 6 = domingo


def enesimo_dia_habil(desde: date, n: int) -> date:
    """La fecha que es el n-ésimo día hábil después de `desde` (sin incluirlo)."""
    contador = 0
    actual = desde
    while contador < n:
        actual += timedelta(days=1)
        if es_dia_habil(actual):
            contador += 1
    return actual


def limite_gracia_en_utc(vence_en: date, dias_gracia: int) -> datetime:
    """
    Instante UTC del corte de la ventana de gracia: mediodía hora Ecuador
    del n-ésimo día hábil después de `vence_en`. Después de este instante
    la cuenta pasa de 'en_gracia' a 'vencida'.
    """
    dia_limite = enesimo_dia_habil(vence_en, dias_gracia)
    return inicio_dia_ecuador_en_utc(dia_limite) + timedelta(hours=12)
