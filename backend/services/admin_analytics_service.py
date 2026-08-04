"""
Analíticas de plataforma para el superadmin (frontend-admin/): cuántos gyms,
cuánta gente, cuánta venta hay corriendo por todo el sistema. Antes vivía
entero en routes/admin_analytics.py — se mueve acá por el mismo criterio que
el resto de services/.

Todo se calcula con queries agrupadas por gym_id (una consulta por métrica,
sin loop por gym) — mismo criterio que batch_saldos en services/membresia_service.py.

IMPORTANTE: recibe siempre una sesión de get_db_platform (rol app_platform),
nunca get_db. Estas queries leen Miembro/Instructor/Membresia/Asistencia/Venta
sin ningún gym_id (a propósito — es analítica cross-tenant), y esas tablas
tienen RLS real. Con la conexión normal (rol app_backend) esto devuelve 0
filas siempre, no un error — fácil de no notar. app_platform bypassea RLS a
propósito para este caso de uso legítimo.
"""
from datetime import date

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from models import (
    Gimnasio, Usuario, Instructor, Miembro, Membresia, Asistencia, Venta,
    PagoSaas, EstadoVenta, EstadoPagoSaas,
)
from services.suscripciones_service import calcular_saas_estado


def _contar_simple(db: Session, modelo, *filtros) -> dict:
    """{gym_id: count} a partir de un GROUP BY (gym_id) sobre `modelo`."""
    filas = (
        db.query(modelo.gym_id, func.count())
        .filter(*filtros)
        .group_by(modelo.gym_id)
        .all()
    )
    return {gym_id: cantidad for gym_id, cantidad in filas}


def _sumar_simple(db: Session, columna_suma, gym_id_col, *filtros) -> dict:
    filas = (
        db.query(gym_id_col, func.sum(columna_suma))
        .filter(*filtros)
        .group_by(gym_id_col)
        .all()
    )
    return {gym_id: float(total or 0) for gym_id, total in filas}


def _maximo_simple(db: Session, columna_fecha, gym_id_col, *filtros) -> dict:
    filas = (
        db.query(gym_id_col, func.max(columna_fecha))
        .filter(*filtros)
        .group_by(gym_id_col)
        .all()
    )
    return {gym_id: fecha for gym_id, fecha in filas}


def calcular_analytics_por_gym(db: Session) -> list[dict]:
    """Una fila por gym con staff, instructores por tipo, miembros, ventas del mes y actividad."""
    hoy = date.today()
    mes_actual, anio_actual = hoy.month, hoy.year

    gyms = db.query(Gimnasio).order_by(Gimnasio.nombre).all()

    usuarios_por_rol: dict = {}
    for gym_id, rol, cantidad in (
        db.query(Usuario.gym_id, Usuario.rol, func.count())
        .group_by(Usuario.gym_id, Usuario.rol)
        .all()
    ):
        usuarios_por_rol.setdefault(gym_id, {})[rol] = cantidad

    instructores_por_tipo: dict = {}
    for gym_id, tipo, cantidad in (
        db.query(Instructor.gym_id, Instructor.tipo, func.count())
        .group_by(Instructor.gym_id, Instructor.tipo)
        .all()
    ):
        instructores_por_tipo.setdefault(gym_id, {})[tipo] = cantidad

    miembros_activos       = _contar_simple(db, Miembro, Miembro.activo == True)
    miembros_total         = _contar_simple(db, Miembro)
    ventas_total           = _contar_simple(db, Venta)
    membresias_total       = _contar_simple(db, Membresia)
    asistencias_total      = _contar_simple(db, Asistencia)

    ventas_mes_cantidad = _contar_simple(
        db, Venta,
        Venta.estado != EstadoVenta.cancelada,
        extract("month", Venta.creado_en) == mes_actual,
        extract("year",  Venta.creado_en) == anio_actual,
    )
    ventas_mes_monto = _sumar_simple(
        db, Venta.total, Venta.gym_id,
        Venta.estado != EstadoVenta.cancelada,
        extract("month", Venta.creado_en) == mes_actual,
        extract("year",  Venta.creado_en) == anio_actual,
    )

    ultima_venta       = _maximo_simple(db, Venta.creado_en, Venta.gym_id)
    ultima_asistencia  = _maximo_simple(db, Asistencia.fecha, Asistencia.gym_id)

    filas = []
    for g in gyms:
        tipos_instructor = instructores_por_tipo.get(g.id, {})
        roles_usuario     = usuarios_por_rol.get(g.id, {})

        ultimas = [d for d in (ultima_venta.get(g.id), ultima_asistencia.get(g.id)) if d is not None]
        ultima_actividad = max(ultimas) if ultimas else None

        dias_restantes = None
        if g.saas_vence_en:
            dias_restantes = (g.saas_vence_en - hoy).days
        elif g.saas_trial_hasta:
            dias_restantes = (g.saas_trial_hasta - hoy).days

        filas.append({
            "id":               str(g.id),
            "nombre":           g.nombre,
            "slug":             g.slug,
            "email":            g.email,
            "vertical":         g.vertical,
            "activo":           g.activo,
            "creado_en":        g.creado_en,
            "saas_plan":        g.saas_plan,
            "saas_estado":      calcular_saas_estado(g, hoy),
            "saas_tier":        g.saas_tier,
            "saas_vence_en":    g.saas_vence_en,
            "dias_restantes":   dias_restantes,
            "usuarios_total":   sum(roles_usuario.values()),
            "usuarios_admin":   roles_usuario.get("admin", 0),
            "usuarios_staff":   roles_usuario.get("staff", 0),
            "instructores_total":     sum(tipos_instructor.values()),
            "instructores_por_tipo":  {
                "entrenador": tipos_instructor.get("entrenador", 0),
                "doctor":     tipos_instructor.get("doctor", 0),
                "asistente":  tipos_instructor.get("asistente", 0),
            },
            "miembros_total":   miembros_total.get(g.id, 0),
            "miembros_activos": miembros_activos.get(g.id, 0),
            "ventas_mes_actual": {
                "cantidad": ventas_mes_cantidad.get(g.id, 0),
                "monto":    round(ventas_mes_monto.get(g.id, 0.0), 2),
            },
            # Proxy de actividad/volumen de datos — NO es tamaño real en disco,
            # Postgres no expone eso barato por tenant. Es la suma de filas de
            # negocio del gym en las tablas de mayor volumen.
            "registros_total": (
                miembros_total.get(g.id, 0)
                + ventas_total.get(g.id, 0)
                + membresias_total.get(g.id, 0)
                + asistencias_total.get(g.id, 0)
            ),
            "ultima_actividad": ultima_actividad,
        })

    return filas


def calcular_resumen_plataforma(db: Session) -> dict:
    """Totales de toda la plataforma."""
    hoy = date.today()
    mes_actual, anio_actual = hoy.month, hoy.year

    gyms = db.query(Gimnasio).all()
    gyms_por_vertical: dict = {}
    gyms_por_estado_saas: dict = {}
    for g in gyms:
        gyms_por_vertical[g.vertical] = gyms_por_vertical.get(g.vertical, 0) + 1
        estado_vivo = calcular_saas_estado(g, hoy)
        gyms_por_estado_saas[estado_vivo] = gyms_por_estado_saas.get(estado_vivo, 0) + 1

    usuarios_total      = db.query(func.count(Usuario.id)).scalar() or 0
    instructores_total  = db.query(func.count(Instructor.id)).scalar() or 0
    instructores_por_tipo_filas = (
        db.query(Instructor.tipo, func.count()).group_by(Instructor.tipo).all()
    )
    instructores_por_tipo = {tipo: cantidad for tipo, cantidad in instructores_por_tipo_filas}

    miembros_total    = db.query(func.count(Miembro.id)).scalar() or 0
    miembros_activos  = db.query(func.count(Miembro.id)).filter(Miembro.activo == True).scalar() or 0

    ventas_mes_cantidad = (
        db.query(func.count(Venta.id))
        .filter(
            Venta.estado != EstadoVenta.cancelada,
            extract("month", Venta.creado_en) == mes_actual,
            extract("year",  Venta.creado_en) == anio_actual,
        )
        .scalar() or 0
    )
    ventas_mes_monto = (
        db.query(func.sum(Venta.total))
        .filter(
            Venta.estado != EstadoVenta.cancelada,
            extract("month", Venta.creado_en) == mes_actual,
            extract("year",  Venta.creado_en) == anio_actual,
        )
        .scalar() or 0
    )

    revenue_saas_mes_actual = (
        db.query(func.sum(PagoSaas.monto))
        .filter(
            PagoSaas.estado == EstadoPagoSaas.confirmado,
            extract("month", PagoSaas.confirmado_en) == mes_actual,
            extract("year",  PagoSaas.confirmado_en) == anio_actual,
        )
        .scalar() or 0
    )
    revenue_saas_historico = (
        db.query(func.sum(PagoSaas.monto))
        .filter(PagoSaas.estado == EstadoPagoSaas.confirmado)
        .scalar() or 0
    )

    return {
        "gyms_total":            len(gyms),
        "gyms_por_vertical":     gyms_por_vertical,
        "gyms_por_estado_saas":  gyms_por_estado_saas,
        "usuarios_total":        usuarios_total,
        "instructores_total":    instructores_total,
        "instructores_por_tipo": {
            "entrenador": instructores_por_tipo.get("entrenador", 0),
            "doctor":     instructores_por_tipo.get("doctor", 0),
            "asistente":  instructores_por_tipo.get("asistente", 0),
        },
        "miembros_total":         miembros_total,
        "miembros_activos":       miembros_activos,
        "ventas_mes_actual": {
            "cantidad": ventas_mes_cantidad,
            "monto":    round(float(ventas_mes_monto), 2),
        },
        "revenue_saas_mes_actual": round(float(revenue_saas_mes_actual), 2),
        "revenue_saas_historico":  round(float(revenue_saas_historico), 2),
    }
