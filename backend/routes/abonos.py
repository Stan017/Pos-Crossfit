from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from models import Venta, VentaItem, Pago, EstadoVenta, MetodoPago
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from dinero import redondear
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from security import sanitizar
from limiter import limiter

router = APIRouter()


class PagoCreate(BaseModel):
    monto:  float = Field(gt=0)
    metodo: MetodoPago = MetodoPago.efectivo
    notas:  Optional[str] = None

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


@router.get("/")
def listar_abonos(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Ventas POS con saldo pendiente (estado = abono)."""
    ventas = (
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
            joinedload(Venta.pagos),
        )
        .filter(
            Venta.gym_id == usuario.gym_id,
            Venta.estado == EstadoVenta.abono,
        )
        .order_by(Venta.creado_en.desc())
        .all()
    )
    resultado = []
    for v in ventas:
        total_pagado = sum(p.monto for p in v.pagos)
        saldo = redondear(v.total - total_pagado)
        resultado.append({
            "venta": {
                "id":        v.id,
                "creado_en": v.creado_en,
                "total":     v.total,
                "notas":     v.notas,
                "miembro": {
                    "id":      v.miembro.id,
                    "nombre":  v.miembro.nombre,
                    "apellido": v.miembro.apellido,
                } if v.miembro else None,
                "items": [
                    {
                        "id":              i.id,
                        "cantidad":        i.cantidad,
                        "precio_unitario": i.precio_unitario,
                        "subtotal":        i.subtotal,
                        "producto": {
                            "id":     i.producto.id,
                            "nombre": i.producto.nombre,
                        } if i.producto else None,
                    }
                    for i in v.items
                ],
            },
            "total_pagado": redondear(total_pagado),
            "saldo":        saldo,
        })
    return resultado


@router.get("/{venta_id}")
def detalle_abono(
    venta_id: int,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = (
        db.query(Venta)
        .options(joinedload(Venta.pagos))
        .filter(Venta.id == venta_id, Venta.gym_id == usuario.gym_id)
        .first()
    )
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    total_pagado = sum(p.monto for p in venta.pagos)
    saldo = redondear(venta.total - total_pagado)
    return {
        "pagos": [
            {
                "id":     p.id,
                "monto":  p.monto,
                "metodo": p.metodo,
                "fecha":  p.fecha,
                "notas":  p.notas,
            }
            for p in venta.pagos
        ],
        "total_pagado": redondear(total_pagado),
        "saldo":        saldo,
    }


@router.post("/{venta_id}/pagar", status_code=201)
@limiter.limit("30/minute")
def registrar_abono(
    request:  Request,
    venta_id: int,
    data:     PagoCreate,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    """Registra un abono. Si el pago cubre el saldo, cierra la venta como pagada."""
    # with_for_update() previene que dos abonos concurrentes lean el mismo
    # saldo antes de que ninguno confirme, lo que permitiría sobrepagar la venta
    venta = db.query(Venta).filter(
        Venta.id == venta_id, Venta.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    if venta.estado == EstadoVenta.pagada:
        raise HTTPException(status_code=400, detail="Esta venta ya está completamente pagada.")

    total_pagado = db.query(func.sum(Pago.monto)).filter(Pago.venta_id == venta_id).scalar() or 0
    saldo = redondear(venta.total - total_pagado)

    monto_dec = redondear(data.monto)
    if monto_dec > saldo:
        raise HTTPException(
            status_code=400,
            detail=f"El pago ({data.monto:.2f}) supera el saldo pendiente ({saldo:.2f})."
        )

    pago = Pago(
        gym_id   = venta.gym_id,
        venta_id = venta_id,
        monto    = monto_dec,
        metodo   = data.metodo,
        notas    = data.notas,
    )
    db.add(pago)

    if redondear(saldo - monto_dec) == 0:
        venta.estado = EstadoVenta.pagada

    db.commit()
    db.refresh(pago)
    return pago
