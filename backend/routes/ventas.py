from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from models import Venta, VentaItem, Pago, Producto, EstadoVenta, MetodoPago, Miembro
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from dinero import a_decimal, redondear
from security import sanitizar
from services.venta_service import calcular_montos, calcular_estado_venta
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

router = APIRouter()


# ─── Schemas ───────────────────────────────────────────────────────────────────

class ItemVentaSchema(BaseModel):
    # precio_unitario NO viene del cliente: el precio siempre se toma de
    # Producto.precio_venta al momento de la venta (ver crear_venta_y_
    # descontar_stock / reemplazar_items_y_recalcular_stock) — de lo
    # contrario cualquier staff podría vender a cualquier precio sin dejar
    # rastro de que se apartó del catálogo.
    producto_id: int
    cantidad:    int = Field(gt=0)


class VentaCreate(BaseModel):
    miembro_id:   Optional[int]   = None
    porcentaje_iva: float         = Field(default=0.0, ge=0)
    items:        List[ItemVentaSchema]
    pago_inicial: float           = Field(default=0.0, ge=0)
    metodo_pago:  MetodoPago      = MetodoPago.efectivo
    notas:        Optional[str]   = None

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class VentaUpdate(BaseModel):
    notas:      Optional[str] = None
    miembro_id: Optional[int] = None  # 0 = quitar miembro

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class VentaItemsUpdate(BaseModel):
    items:          List[ItemVentaSchema]
    porcentaje_iva: Optional[float] = Field(default=None, ge=0)


class CostoExtraInput(BaseModel):
    """Cargo puntual sin producto de catálogo detrás (ej. un servicio que el
    cliente pidió y no está dado de alta como producto)."""
    descripcion: str           = Field(min_length=1, max_length=200)
    monto:       float         = Field(gt=0)
    notas:       Optional[str] = None

    @field_validator("descripcion", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _serializar_venta(v: Venta) -> dict:
    return {
        "id":             v.id,
        "creado_en":      v.creado_en,
        "subtotal":       v.subtotal,
        "porcentaje_iva": v.porcentaje_iva,
        "monto_iva":      v.monto_iva,
        "total":          v.total,
        "estado":         v.estado,
        "notas":          v.notas,
        "miembro": {
            "id":       v.miembro.id,
            "nombre":   v.miembro.nombre,
            "apellido": v.miembro.apellido,
            "cedula":   v.miembro.cedula,
        } if v.miembro else None,
        "items": [
            {
                "id":                i.id,
                "producto_id":       i.producto_id,
                "cantidad":          i.cantidad,
                "precio_unitario":   i.precio_unitario,
                "subtotal":          i.subtotal,
                "descripcion_libre": i.descripcion_libre,
                "notas":             i.notas,
                "producto": {
                    "id":     i.producto.id,
                    "nombre": i.producto.nombre,
                } if i.producto else None,
            }
            for i in v.items
        ],
        "pagos": [
            {
                "id":     p.id,
                "monto":  p.monto,
                "metodo": p.metodo,
                "fecha":  p.fecha,
                "notas":  p.notas,
            }
            for p in v.pagos
        ],
    }


# ─── Rutas ─────────────────────────────────────────────────────────────────────

@router.get("/")
def listar_ventas(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    ventas = (
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
            joinedload(Venta.pagos),
        )
        .filter(Venta.gym_id == usuario.gym_id)
        .order_by(Venta.creado_en.desc())
        .all()
    )
    return [_serializar_venta(v) for v in ventas]


@router.get("/{venta_id}")
def obtener_venta(
    venta_id: int,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = (
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
            joinedload(Venta.pagos),
        )
        .filter(Venta.id == venta_id, Venta.gym_id == usuario.gym_id)
        .first()
    )
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    return _serializar_venta(venta)


@router.post("/", status_code=201)
def crear_venta_y_descontar_stock(
    data:    VentaCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    if not data.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un ítem.")

    if data.miembro_id is not None:
        if not db.query(Miembro).filter(
            Miembro.id     == data.miembro_id,
            Miembro.gym_id == usuario.gym_id,
        ).first():
            raise HTTPException(status_code=404, detail="Miembro no encontrado.")

    # El precio se toma siempre de Producto.precio_venta (no del cliente) —
    # por eso este primer paso ya deja todo listo para crear los VentaItem
    # antes de conocer subtotal/total, que dependen de ese mismo precio.
    items_a_crear = []
    subtotal = a_decimal(0)
    # Orden ascendente por producto_id: si dos ventas concurrentes comparten
    # productos, ambas deben pedir los locks en el mismo orden global — si no,
    # una venta bloquea A y espera B mientras la otra bloquea B y espera A
    # (deadlock detectado y abortado por Postgres).
    for item in sorted(data.items, key=lambda i: i.producto_id):
        # with_for_update() previene que dos ventas concurrentes lean el mismo
        # stock antes de que ninguna confirme, lo que permitiría vender más
        # unidades de las que hay disponibles (sobreventa)
        producto = db.query(Producto).filter(
            Producto.id     == item.producto_id,
            Producto.gym_id == usuario.gym_id,
            Producto.activo == True,
        ).with_for_update().first()
        if not producto:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail=f"Producto {item.producto_id} no encontrado."
            )
        if producto.stock < item.cantidad:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para '{producto.nombre}'. Disponible: {producto.stock}."
            )
        producto.stock -= item.cantidad
        precio_unitario_dec = a_decimal(producto.precio_venta)
        subtotal_item        = redondear(item.cantidad * precio_unitario_dec)
        subtotal += subtotal_item
        items_a_crear.append({
            "producto_id":     item.producto_id,
            "cantidad":        item.cantidad,
            "precio_unitario": precio_unitario_dec,
            "costo_unitario":  producto.precio_costo,
            "subtotal":        subtotal_item,
        })

    monto_iva, total = calcular_montos(subtotal, data.porcentaje_iva)
    estado = calcular_estado_venta(data.pago_inicial, total)

    venta = Venta(
        gym_id         = usuario.gym_id,
        miembro_id     = data.miembro_id,
        subtotal       = redondear(subtotal),
        porcentaje_iva = data.porcentaje_iva,
        monto_iva      = monto_iva,
        total          = total,
        estado         = estado,
        notas          = data.notas,
        creado_por     = usuario.user_id,
    )
    db.add(venta)
    db.flush()

    for datos_item in items_a_crear:
        db.add(VentaItem(venta_id=venta.id, **datos_item))

    if data.pago_inicial > 0:
        db.add(Pago(
            gym_id   = usuario.gym_id,
            venta_id = venta.id,
            monto    = a_decimal(data.pago_inicial),
            metodo   = data.metodo_pago,
        ))

    db.commit()
    db.refresh(venta)
    return _serializar_venta(
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
            joinedload(Venta.pagos),
        )
        .filter(Venta.id == venta.id)
        .first()
    )


@router.patch("/{venta_id}")
def actualizar_venta(
    venta_id: int,
    data:     VentaUpdate,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = db.query(Venta).filter(
        Venta.id == venta_id, Venta.gym_id == usuario.gym_id,
    ).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")

    if data.notas is not None:
        venta.notas = data.notas or None

    if data.miembro_id is not None:
        if data.miembro_id <= 0:
            venta.miembro_id = None
        else:
            if not db.query(Miembro).filter(
                Miembro.id     == data.miembro_id,
                Miembro.gym_id == usuario.gym_id,
            ).first():
                raise HTTPException(status_code=404, detail="Miembro no encontrado.")
            venta.miembro_id = data.miembro_id

    db.commit()
    db.refresh(venta)
    return venta


@router.patch("/{venta_id}/items")
def reemplazar_items_y_recalcular_stock(
    venta_id: int,
    data:     VentaItemsUpdate,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = (
        db.query(Venta)
        .options(joinedload(Venta.items), joinedload(Venta.pagos))
        .filter(Venta.id == venta_id, Venta.gym_id == usuario.gym_id)
        .first()
    )
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    if not data.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un ítem.")

    # with_for_update() en las tres queries de Producto de esta función:
    # previene que otra venta concurrente lea/modifique el mismo stock entre
    # el momento en que lo restauramos, lo validamos, y lo volvemos a
    # descontar — sin esto, dos requests podrían sobrevender igual que en
    # crear_venta_y_descontar_stock.

    # 1. Restaurar stock de ítems actuales
    # Sin filtro de activo: si el producto fue desactivado después de la
    # venta, su stock contable sigue siendo real y debe restaurarse igual.
    # Orden ascendente por producto_id en los tres pasos de esta función que
    # bloquean filas de Producto: dos requests concurrentes sobre productos
    # compartidos deben pedir los locks en el mismo orden global, o Postgres
    # aborta por deadlock (ver mismo comentario en crear_venta_y_descontar_stock).
    for item in sorted(venta.items, key=lambda i: (i.producto_id is None, i.producto_id)):
        prod = db.query(Producto).filter(
            Producto.id     == item.producto_id,
            Producto.gym_id == usuario.gym_id,
        ).with_for_update().first()
        if prod:
            prod.stock += item.cantidad

    # 2. Validar stock disponible para los nuevos ítems
    for item in sorted(data.items, key=lambda i: i.producto_id):
        prod = db.query(Producto).filter(
            Producto.id     == item.producto_id,
            Producto.gym_id == usuario.gym_id,
        ).with_for_update().first()
        if not prod:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado.")
        if prod.stock < item.cantidad:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para '{prod.nombre}'. Disponible: {prod.stock}."
            )

    # 3. Borrar ítems de producto viejos — NO los de costo extra
    # (producto_id NULL, ver agregar_costo_extra_y_recalcular_totales):
    # ItemVentaSchema exige producto_id, así que nunca pueden venir en
    # data.items. Borrarlos acá los perdía para siempre sin que el total
    # nuevo los reflejara — el cargo desaparecía en silencio.
    subtotal_costo_extra = sum(
        (a_decimal(item.subtotal) for item in venta.items if item.producto_id is None),
        a_decimal(0),
    )
    for item in list(venta.items):
        if item.producto_id is not None:
            db.delete(item)
    db.flush()

    # 4. Crear nuevos ítems y descontar stock
    nuevo_subtotal = subtotal_costo_extra
    for item in sorted(data.items, key=lambda i: i.producto_id):
        prod = db.query(Producto).filter(
            Producto.id     == item.producto_id,
            Producto.gym_id == usuario.gym_id,
        ).with_for_update().first()
        prod.stock -= item.cantidad
        precio_unitario_dec = a_decimal(prod.precio_venta)
        subtotal_item = redondear(item.cantidad * precio_unitario_dec)
        nuevo_subtotal += subtotal_item
        db.add(VentaItem(
            venta_id        = venta_id,
            producto_id     = item.producto_id,
            cantidad        = item.cantidad,
            precio_unitario = precio_unitario_dec,
            costo_unitario  = prod.precio_costo,
            subtotal        = subtotal_item,
        ))

    # 5. Recalcular totales
    pct_iva = data.porcentaje_iva if data.porcentaje_iva is not None else venta.porcentaje_iva
    nuevo_subtotal = redondear(nuevo_subtotal)
    nuevo_monto_iva, nuevo_total = calcular_montos(nuevo_subtotal, pct_iva)

    venta.subtotal       = nuevo_subtotal
    venta.porcentaje_iva = pct_iva
    venta.monto_iva      = nuevo_monto_iva
    venta.total          = nuevo_total

    total_pagado = sum(p.monto for p in venta.pagos)
    venta.estado = calcular_estado_venta(total_pagado, nuevo_total)

    db.commit()
    db.refresh(venta)
    return venta


@router.post("/{venta_id}/costo-extra", status_code=201)
def agregar_costo_extra_y_recalcular_totales(
    venta_id: int,
    data:     CostoExtraInput,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    """
    Agrega un cargo puntual a una venta ya existente, sin producto de
    catálogo detrás (ej. algo que el cliente pidió y no está en inventario).
    No toca stock porque no hay producto real. Recalcula el total con el
    mismo porcentaje_iva que ya tenía la venta, y re-evalúa el estado: si
    esto deja saldo pendiente en una venta que ya estaba "pagada", pasa a
    "abono" — mismo criterio que reemplazar_items_y_recalcular_stock.
    """
    # with_for_update() previene que dos costos extra concurrentes sobre la
    # misma venta lean el mismo subtotal viejo y cada uno pise el total del
    # otro al commitear (mismo criterio que el resto de esta ruta y que
    # abonos.py). Sin joinedload acá a propósito: with_for_update() no se
    # combina con joins en este código (ver el resto de las rutas) — y esta
    # función no lee venta.items en ningún lado, solo agrega uno nuevo.
    venta = (
        db.query(Venta)
        .filter(Venta.id == venta_id, Venta.gym_id == usuario.gym_id)
        .with_for_update()
        .first()
    )
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    if venta.estado == EstadoVenta.cancelada:
        raise HTTPException(status_code=409, detail="No se puede agregar un costo a una venta cancelada.")

    monto_dec = a_decimal(data.monto)
    db.add(VentaItem(
        venta_id          = venta_id,
        producto_id       = None,
        descripcion_libre = data.descripcion,
        cantidad          = 1,
        precio_unitario   = monto_dec,
        costo_unitario    = 0,
        subtotal          = redondear(monto_dec),
        notas             = data.notas,
    ))

    nuevo_subtotal = redondear(a_decimal(venta.subtotal) + monto_dec)
    nuevo_monto_iva, nuevo_total = calcular_montos(nuevo_subtotal, venta.porcentaje_iva)

    venta.subtotal  = nuevo_subtotal
    venta.monto_iva = nuevo_monto_iva
    venta.total     = nuevo_total

    total_pagado = sum(a_decimal(p.monto) for p in venta.pagos)
    venta.estado = calcular_estado_venta(total_pagado, nuevo_total)

    db.commit()
    return _serializar_venta(
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
            joinedload(Venta.pagos),
        )
        .filter(Venta.id == venta_id)
        .first()
    )


@router.delete("/{venta_id}", status_code=204)
def eliminar_venta_y_restaurar_stock(
    venta_id: int,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = (
        db.query(Venta)
        .options(joinedload(Venta.items), joinedload(Venta.pagos))
        .filter(Venta.id == venta_id, Venta.gym_id == usuario.gym_id)
        .first()
    )
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")

    # Venta.pagos tiene cascade="all, delete-orphan" — sin este chequeo,
    # borrar la venta se lleva puestos sus pagos ya cobrados, sin rastro
    # (migración 002 excluye pagos de la auditoría a propósito, así que
    # tampoco queda registro ahí). Una venta sin pagos es un error recién
    # hecho, sin plata de por medio — esa sí se puede borrar sin más.
    if venta.pagos:
        raise HTTPException(
            status_code=409,
            detail="Esta venta ya tiene pagos registrados — eliminarla borraría ese historial de cobro. No está permitido.",
        )

    # Sin filtro de activo: ver comentario en reemplazar_items_y_recalcular_stock.
    # with_for_update() por la misma razón que en el resto de esta ruta.
    # Orden ascendente por producto_id: mismo motivo anti-deadlock que en
    # crear_venta_y_descontar_stock / reemplazar_items_y_recalcular_stock.
    for item in sorted(venta.items, key=lambda i: (i.producto_id is None, i.producto_id)):
        producto = db.query(Producto).filter(
            Producto.id     == item.producto_id,
            Producto.gym_id == usuario.gym_id,
        ).with_for_update().first()
        if producto:
            producto.stock += item.cantidad

    db.delete(venta)
    db.commit()
