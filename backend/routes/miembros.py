from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date

from models import Miembro, Membresia
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from security import sanitizar
from services.membresia_service import calcular_estado, batch_saldos, ESTADOS_VIGENTES
from dinero import a_decimal

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class MiembroInput(BaseModel):
    nombre:              str
    apellido:            str
    fecha_ingreso:       date
    email:               Optional[str] = None
    telefono:            Optional[str] = None
    cedula:              Optional[str] = None
    fecha_nacimiento:    Optional[date] = None
    contacto_emergencia: Optional[str] = None
    peso:                Optional[float] = Field(default=None, gt=0)
    altura:              Optional[float] = Field(default=None, gt=0)
    foto_url:            Optional[str] = None
    notas:               Optional[str] = None

    @field_validator("nombre", "apellido", "email", "telefono", "cedula", "contacto_emergencia", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)

class MiembroUpdate(BaseModel):
    nombre:              Optional[str]  = None
    apellido:            Optional[str]  = None
    fecha_ingreso:       Optional[date] = None
    email:               Optional[str]  = None
    telefono:            Optional[str]  = None
    cedula:              Optional[str]  = None
    fecha_nacimiento:    Optional[date] = None
    contacto_emergencia: Optional[str]  = None
    peso:                Optional[float] = Field(default=None, gt=0)
    altura:              Optional[float] = Field(default=None, gt=0)
    foto_url:            Optional[str]  = None
    notas:               Optional[str]  = None
    activo:              Optional[bool] = None

    @field_validator("nombre", "apellido", "email", "telefono", "cedula", "contacto_emergencia", "notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)

    # nombre/apellido/fecha_ingreso son NOT NULL en la tabla. Con
    # exclude_unset=True (ver actualizar_miembro), un cliente que mande
    # {"nombre": null} para "vaciarlo" ya no se ignora en silencio como
    # antes — sin este chequeo llegaría hasta la DB y explotaría como un
    # IntegrityError sin manejar. El resto de los campos de acá sí son
    # nullable de verdad, ahí un null explícito es correcto: significa
    # "vaciá este dato".
    @field_validator("nombre", "apellido", "fecha_ingreso")
    @classmethod
    def no_permitir_vacio(cls, v):
        if v is None:
            raise ValueError("Este campo no puede quedar vacío.")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verificar_nombre_duplicado(
    db: Session, gym_id, nombre: str, apellido: str, excluir_id: Optional[int] = None
) -> None:
    """
    A diferencia de cédula, nombre+apellido no tiene un constraint en la DB
    (dos personas distintas pueden legítimamente compartir nombre) — esto es
    un aviso de negocio, no una regla dura de integridad, así que se chequea
    acá y no en el schema. Comparación case-insensitive: "steffy" y "Steffy"
    son el mismo duplicado a ojos de quien está cargando el dato a mano.
    """
    query = db.query(Miembro).filter(
        Miembro.gym_id == gym_id,
        func.lower(Miembro.nombre) == nombre.lower(),
        func.lower(Miembro.apellido) == apellido.lower(),
    )
    if excluir_id is not None:
        query = query.filter(Miembro.id != excluir_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un miembro con el nombre {nombre} {apellido}.",
        )


def _membresia_activa(miembro: Miembro, saldos: dict) -> Optional[dict]:
    hoy = date.today()
    candidatas = sorted(miembro.membresias, key=lambda x: x.creado_en, reverse=True)
    for m in candidatas:
        saldo  = saldos.get(m.id, a_decimal(0))
        estado = calcular_estado(m, saldo)
        if estado not in ESTADOS_VIGENTES:
            continue
        dias_restantes    = None
        clases_restantes  = None
        if m.fecha_fin:
            dias_restantes = max(0, (m.fecha_fin - hoy).days)
        elif m.clases_total is not None and m.clases_usadas is not None:
            clases_restantes = max(0, m.clases_total - m.clases_usadas)
        return {
            "id":               m.id,
            "plan_id":          m.plan_id,
            "plan_nombre":      m.plan.nombre if m.plan else None,
            "plan_tipo":        m.plan.tipo   if m.plan else None,
            "estado":           estado,
            "fecha_fin":        m.fecha_fin,
            "dias_restantes":   dias_restantes,
            "clases_restantes": clases_restantes,
        }
    return None


def _serializar(miembro: Miembro, saldos: dict) -> dict:
    return {
        "id":                   miembro.id,
        "nombre":               miembro.nombre,
        "apellido":             miembro.apellido,
        "fecha_ingreso":        miembro.fecha_ingreso,
        "email":                miembro.email,
        "telefono":             miembro.telefono,
        "cedula":               miembro.cedula,
        "fecha_nacimiento":     miembro.fecha_nacimiento,
        "contacto_emergencia":  miembro.contacto_emergencia,
        "peso":                 float(miembro.peso)   if miembro.peso   is not None else None,
        "altura":               float(miembro.altura) if miembro.altura is not None else None,
        "notas":                miembro.notas,
        "activo":               miembro.activo,
        "creado_en":            miembro.creado_en,
        "membresia_activa":     _membresia_activa(miembro, saldos),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def listar_miembros(
    q:      Optional[str]  = Query(None),
    activo: Optional[bool] = Query(None),
    db:     Session        = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    query = (
        db.query(Miembro)
        .options(
            joinedload(Miembro.membresias).joinedload(Membresia.plan)
        )
        .filter(Miembro.gym_id == usuario.gym_id)
    )
    if activo is not None:
        query = query.filter(Miembro.activo == activo)
    if q:
        termino = f"%{q}%"
        query = query.filter(
            Miembro.nombre.ilike(termino) |
            Miembro.apellido.ilike(termino) |
            Miembro.cedula.ilike(termino)
        )
    miembros = query.order_by(Miembro.apellido, Miembro.nombre).all()
    # Una sola query de saldos para toda la lista, no una por miembro — mismo
    # patrón que dashboard.py/deudas.py/planes.py/membresias.py.
    todas_membresias = [m for miembro in miembros for m in miembro.membresias]
    saldos = batch_saldos(todas_membresias, db)
    return [_serializar(m, saldos) for m in miembros]


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_miembro(
    datos:   MiembroInput,
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    _verificar_nombre_duplicado(db, usuario.gym_id, datos.nombre, datos.apellido)

    miembro = Miembro(**datos.model_dump(), gym_id=usuario.gym_id)
    db.add(miembro)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un miembro con esa cédula.",
        ) from e
    db.refresh(miembro)
    miembro = (
        db.query(Miembro)
        .options(joinedload(Miembro.membresias).joinedload(Membresia.plan))
        .filter(Miembro.id == miembro.id)
        .first()
    )
    return _serializar(miembro, batch_saldos(miembro.membresias, db))


@router.get("/{miembro_id}")
def obtener_miembro(
    miembro_id: int,
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    miembro = (
        db.query(Miembro)
        .options(joinedload(Miembro.membresias).joinedload(Membresia.plan))
        .filter(Miembro.id == miembro_id, Miembro.gym_id == usuario.gym_id)
        .first()
    )
    if not miembro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")
    return _serializar(miembro, batch_saldos(miembro.membresias, db))


@router.put("/{miembro_id}")
def actualizar_miembro(
    miembro_id: int,
    datos:      MiembroUpdate,
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    miembro = db.query(Miembro).filter(
        Miembro.id     == miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).first()
    if not miembro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")

    campos = datos.model_dump(exclude_unset=True)
    if "nombre" in campos or "apellido" in campos:
        _verificar_nombre_duplicado(
            db, usuario.gym_id,
            campos.get("nombre", miembro.nombre),
            campos.get("apellido", miembro.apellido),
            excluir_id=miembro_id,
        )

    for campo, valor in campos.items():
        setattr(miembro, campo, valor)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un miembro con esa cédula.",
        ) from e
    miembro = (
        db.query(Miembro)
        .options(joinedload(Miembro.membresias).joinedload(Membresia.plan))
        .filter(Miembro.id == miembro_id)
        .first()
    )
    return _serializar(miembro, batch_saldos(miembro.membresias, db))


@router.patch("/{miembro_id}/reactivar")
def reactivar_miembro(
    miembro_id: int,
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    miembro = db.query(Miembro).filter(
        Miembro.id     == miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).first()
    if not miembro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")
    miembro.activo = True
    db.commit()
    miembro = (
        db.query(Miembro)
        .options(joinedload(Miembro.membresias).joinedload(Membresia.plan))
        .filter(Miembro.id == miembro_id)
        .first()
    )
    return _serializar(miembro, batch_saldos(miembro.membresias, db))


@router.delete("/{miembro_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_miembro(
    miembro_id: int,
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    miembro = db.query(Miembro).filter(
        Miembro.id     == miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).first()
    if not miembro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")
    miembro.activo = False
    db.commit()
