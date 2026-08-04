from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Producto
from auth import get_usuario_actual, require_admin, UsuarioActual, get_db_tenant
from security import sanitizar
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal

router = APIRouter()


# ─── Schemas ───────────────────────────────────────────────────────────────────

class ProductoCreate(BaseModel):
    nombre:       str           = Field(min_length=1, max_length=200)
    categoria:    Optional[str] = Field(default=None, max_length=100)
    precio_venta: Decimal       = Field(ge=0)
    precio_costo: Decimal       = Field(default=0, ge=0)
    stock:        int           = Field(default=0, ge=0)
    stock_minimo: int           = Field(default=0, ge=0)
    codigo_barra: Optional[str] = Field(default=None, max_length=100)
    imagen_url:   Optional[str] = Field(default=None, max_length=300)

    @field_validator("nombre", "categoria", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class ProductoUpdate(BaseModel):
    nombre:       Optional[str]     = Field(default=None, min_length=1, max_length=200)
    categoria:    Optional[str]     = Field(default=None, max_length=100)
    precio_venta: Optional[Decimal] = Field(default=None, ge=0)
    precio_costo: Optional[Decimal] = Field(default=None, ge=0)
    stock:        Optional[int]     = Field(default=None, ge=0)
    stock_minimo: Optional[int]     = Field(default=None, ge=0)
    codigo_barra: Optional[str]     = Field(default=None, max_length=100)
    imagen_url:   Optional[str]     = Field(default=None, max_length=300)
    activo:       Optional[bool]    = None

    @field_validator("nombre", "categoria", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# ─── Rutas ─────────────────────────────────────────────────────────────────────

@router.get("/categorias")
def listar_categorias(
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    rows = (
        db.query(Producto.categoria)
        .filter(
            Producto.gym_id   == usuario.gym_id,
            Producto.activo   == True,
            Producto.categoria != None,
            Producto.categoria != "",
        )
        .distinct()
        .order_by(Producto.categoria)
        .all()
    )
    return [r.categoria for r in rows]


@router.get("/")
def listar_productos(
    q:       Optional[str] = None,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
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


@router.get("/{producto_id}")
def obtener_producto(
    producto_id: int,
    db:          Session       = Depends(get_db_tenant),
    usuario:     UsuarioActual = Depends(get_usuario_actual),
):
    producto = db.query(Producto).filter(
        Producto.id     == producto_id,
        Producto.gym_id == usuario.gym_id,
    ).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return producto


@router.post("/", status_code=201)
def crear_producto(
    data:    ProductoCreate,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    producto = Producto(**data.model_dump(), gym_id=usuario.gym_id)
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.patch("/{producto_id}")
def actualizar_producto(
    producto_id: int,
    data:        ProductoUpdate,
    db:          Session       = Depends(get_db_tenant),
    usuario:     UsuarioActual = Depends(require_admin),
):
    producto = db.query(Producto).filter(
        Producto.id     == producto_id,
        Producto.gym_id == usuario.gym_id,
    ).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(producto, campo, valor)
    db.commit()
    db.refresh(producto)
    return producto


@router.delete("/{producto_id}", status_code=204)
def desactivar_producto(
    producto_id: int,
    db:          Session       = Depends(get_db_tenant),
    usuario:     UsuarioActual = Depends(require_admin),
):
    producto = db.query(Producto).filter(
        Producto.id     == producto_id,
        Producto.gym_id == usuario.gym_id,
    ).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    producto.activo = False
    db.commit()
