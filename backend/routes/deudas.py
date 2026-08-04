from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc

from models import (
    Venta, VentaItem, Pago, EstadoVenta,
    Membresia, EstadoMembresia,
)
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from dinero import a_decimal, redondear
from services.membresia_service import calcular_estado, batch_saldos, precio_acordado_de

router = APIRouter()


@router.get("/")
def listar_deudas(
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    """
    Vista unificada de deudas pendientes del gimnasio:
    - Ventas POS con estado 'abono' (pago parcial)
    - Membresías con estado 'pendiente_pago'
    - Membresías 'vencidas' con saldo > 0 (expiradas pero con deuda)
    """
    resultado = []

    # ── Ventas POS con saldo pendiente ────────────────────────────────────────

    ventas = (
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
        )
        .filter(
            Venta.gym_id == usuario.gym_id,
            Venta.estado == EstadoVenta.abono,
        )
        .all()
    )

    if ventas:
        ids_ventas = [v.id for v in ventas]
        rows = (
            db.query(Pago.venta_id, sqlfunc.sum(Pago.monto))
            .filter(Pago.venta_id.in_(ids_ventas))
            .group_by(Pago.venta_id)
            .all()
        )
        pagados_venta = {row[0]: a_decimal(row[1]) for row in rows}

        for v in ventas:
            pagado    = pagados_venta.get(v.id, a_decimal(0))
            pendiente = redondear(v.total - pagado)
            nombres   = [i.producto.nombre for i in v.items if i.producto]
            descripcion = ", ".join(nombres) if nombres else f"Venta #{v.id}"
            resultado.append({
                "tipo":        "venta",
                "id":          v.id,
                "fecha":       v.creado_en,
                "descripcion": descripcion,
                "miembro": {
                    "id":       v.miembro.id,
                    "nombre":   v.miembro.nombre,
                    "apellido": v.miembro.apellido,
                } if v.miembro else None,
                "total":    v.total,
                "pagado":   redondear(pagado),
                "pendiente": pendiente,
                "estado":   None,
            })

    # ── Membresías con deuda ──────────────────────────────────────────────────
    # No se filtra por Membresia.estado directamente: esa columna solo se
    # actualiza en escrituras (crear/renovar/pagar). Una membresía que venció
    # con saldo pendiente sin que nadie la tocara desde entonces se queda
    # mostrando el último estado guardado (nunca "vencida") — filtrar por la
    # columna la hacía desaparecer de esta vista de deudas en silencio. Se
    # recalcula el estado real de cada membresía no cancelada, igual que
    # listar_membresias()/obtener_alertas() en membresias.py.
    _candidatas = (
        db.query(Membresia)
        .options(joinedload(Membresia.miembro), joinedload(Membresia.plan))
        .filter(
            Membresia.gym_id == usuario.gym_id,
            Membresia.estado != EstadoMembresia.cancelada,
        )
        .all()
    )
    _saldos_candidatas = batch_saldos(_candidatas, db)

    for m in _candidatas:
        saldo = _saldos_candidatas.get(m.id, a_decimal(0))
        if saldo <= 0:
            continue
        estado_real = calcular_estado(m, saldo)
        if estado_real not in (EstadoMembresia.pendiente_pago, EstadoMembresia.vencida):
            continue

        precio_acordado = precio_acordado_de(m)
        pagado = redondear(precio_acordado - saldo)
        resultado.append({
            "tipo":        "membresia",
            "id":          m.id,
            "fecha":       m.creado_en,
            "descripcion": m.plan.nombre if m.plan else f"Membresía #{m.id}",
            "miembro": {
                "id":       m.miembro.id,
                "nombre":   m.miembro.nombre,
                "apellido": m.miembro.apellido,
            } if m.miembro else None,
            "total":     precio_acordado,
            "pagado":    pagado,
            "pendiente": saldo,
            "estado":    estado_real,
        })

    resultado.sort(key=lambda x: x["fecha"], reverse=True)
    return resultado
