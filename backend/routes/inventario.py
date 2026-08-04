from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Producto, VentaItem, Venta
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from typing import Optional

router = APIRouter()


@router.get("/")
def inventario(
    q:       Optional[str] = Query(None),
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Vista completa del inventario. Búsqueda por nombre, categoría o código de barras."""
    query = db.query(Producto).filter(
        Producto.gym_id == usuario.gym_id,
        Producto.activo == True,
    )
    if q:
        filtro = f"%{q}%"
        query = query.filter(
            or_(
                Producto.nombre.ilike(filtro),
                Producto.categoria.ilike(filtro),
                Producto.codigo_barra.ilike(filtro),
            )
        )
    return query.order_by(Producto.nombre).all()


@router.get("/sin-movimiento")
def productos_sin_movimiento(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Productos activos con stock > 0 que nunca han sido vendidos."""
    # filter(producto_id.isnot(None)) es obligatorio, no cosmético: producto_id
    # ahora puede ser NULL (ítems de costo extra sin producto real detrás). Si
    # un solo NULL entra al resultado de esta subquery, "NOT IN" en SQL evalúa
    # a UNKNOWN para cualquier fila — la query de afuera dejaría de devolver
    # productos para TODO el gym apenas exista un costo extra en el historial.
    #
    # join a Venta + filtro de gym_id explícito: VentaItem no tiene columna
    # gym_id propia. Hoy esto ya está protegido porque ventas.py valida que
    # producto_id pertenezca al mismo gym antes de crear el VentaItem — pero
    # esta query no debe depender de ese invariante externo para ser correcta.
    vendidos = (
        db.query(VentaItem.producto_id)
        .join(Venta, Venta.id == VentaItem.venta_id)
        .filter(
            Venta.gym_id == usuario.gym_id,
            VentaItem.producto_id.isnot(None),
        )
        .distinct()
        .scalar_subquery()
    )
    return (
        db.query(Producto)
        .filter(
            Producto.gym_id == usuario.gym_id,
            Producto.activo == True,
            Producto.stock  > 0,
            Producto.id.not_in(vendidos),
        )
        .all()
    )


@router.get("/stock-bajo")
def stock_bajo(
    limite:  int     = Query(default=3, ge=0),
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Productos con stock menor o igual al stock_minimo configurado (o al límite dado)."""
    return (
        db.query(Producto)
        .filter(
            Producto.gym_id == usuario.gym_id,
            Producto.activo == True,
            Producto.stock  <= Producto.stock_minimo,
        )
        .order_by(Producto.stock)
        .all()
    )
