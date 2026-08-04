from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload

from database import get_db_platform
from models import Gimnasio, PagoSaas, SaasPlan, SaasEstado, SaasTier, EstadoPagoSaas, MetodoPago
from auth import get_usuario_actual, require_admin, UsuarioActual, get_db_tenant
from services.suscripciones_service import calcular_saas_estado, sincronizar_estado_saas_en_db
from security import sanitizar
from storage import guardar_imagen, borrar_archivo
from platform_admin import require_platform_admin, get_db_platform_admin
from limiter import limiter

# ── Routers ───────────────────────────────────────────────────────────────────

gym_router   = APIRouter()   # rutas del gym admin  → prefix="/suscripciones"
admin_router = APIRouter()   # rutas del superadmin → prefix="/admin/suscripciones"

# ── Planes y precios ──────────────────────────────────────────────────────────

SAAS_PLANES: dict[str, dict] = {
    "mensual":    {"dias": 30,  "precio": Decimal("45.00")},
    "trimestral": {"dias": 90,  "precio": Decimal("120.00")},
    "semestral":  {"dias": 180, "precio": Decimal("220.00")},
    "anual":      {"dias": 365, "precio": Decimal("400.00")},
}

# Precio propio del tier "solo" — separado de SAAS_PLANES a propósito, para
# no tocarle el precio a nadie que ya esté en estandar/clinica/personalizado.
# Sin trimestral: mismo descuento por compromiso más largo que el resto de
# los planes (5x mensual = 1 mes gratis en semestral, 10x = 2 meses gratis
# en anual — igual que SAAS_PLANES y que la página de marketing), pero sin
# saltar a un período intermedio que este tier no necesita.
SAAS_PLANES_SOLO: dict[str, dict] = {
    "mensual":   {"dias": 30,  "precio": Decimal("20.00")},
    "semestral": {"dias": 180, "precio": Decimal("100.00")},
    "anual":     {"dias": 365, "precio": Decimal("200.00")},
}

# Tiers que un gym puede pedir por autoservicio junto con su solicitud de
# pago (routes/suscripciones.py: solicitar_suscripcion). trial no aplica (no
# se "solicita", es el estado inicial) y personalizado es siempre un trato
# negociado a mano por el platform admin — nunca autoservicio.
TIERS_AUTOSERVICIO = {SaasTier.solo, SaasTier.estandar, SaasTier.clinica}

# ── Schemas ───────────────────────────────────────────────────────────────────

class ConfirmarPagoIn(BaseModel):
    pago_saas_id:  int
    confirmado_por: str   # nombre/email del superadmin que confirma

    @field_validator("confirmado_por", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class RechazarPagoIn(BaseModel):
    pago_saas_id:  int
    razon_rechazo: Optional[str] = None

    @field_validator("razon_rechazo", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


class CambiarTierIn(BaseModel):
    tier: SaasTier


class SuspenderIn(BaseModel):
    notas: Optional[str] = None

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nueva_fecha_vencimiento(plan: SaasPlan, desde: date) -> date:
    return desde + timedelta(days=SAAS_PLANES[plan.value]["dias"])


# ── Endpoints del gym admin ───────────────────────────────────────────────────

@gym_router.get("/estado")
@limiter.limit("30/minute")
def estado_suscripcion(
    request: Request,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Estado actual de la suscripción del gimnasio. Accesible aunque esté vencida."""
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == usuario.gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")

    hoy = date.today()
    sincronizar_estado_saas_en_db(gimnasio, db)

    dias_restantes = None
    if gimnasio.saas_vence_en:
        dias_restantes = (gimnasio.saas_vence_en - hoy).days
    elif gimnasio.saas_trial_hasta:
        dias_restantes = (gimnasio.saas_trial_hasta - hoy).days

    pago_pendiente = (
        db.query(PagoSaas)
        .filter(
            PagoSaas.gym_id == usuario.gym_id,
            PagoSaas.estado == EstadoPagoSaas.pendiente,
        )
        .order_by(PagoSaas.solicitado_en.desc())
        .first()
    )

    # Cada opción es {tier, plan, precio, dias}. tier=None = renovar el tier
    # actual del gimnasio, sin pedir cambio.
    #
    # "solo" es un caso aparte: SAAS_PLANES (mensual/trimestral/semestral/anual)
    # es el precio de estandar/clinica/personalizado, NUNCA el de un gimnasio
    # que ya está en "solo" — mezclarlos hacía que un gym en Solo viera (y
    # pagara) $45 al "renovar" en vez de sus $20 reales. Si el gimnasio ya
    # está en "solo", las únicas opciones son las de SAAS_PLANES_SOLO. Si no,
    # se ofrecen los planes normales más la opción de pasarse a Solo
    # (autoservicio, en cualquiera de sus períodos) — mismo criterio que
    # cambiar_tier (admin_router) usa para rechazar un cambio a un tier
    # igual al actual.
    if gimnasio.saas_tier == SaasTier.solo:
        planes_disponibles = [
            {"tier": SaasTier.solo, "plan": plan, "precio": cfg["precio"], "dias": cfg["dias"]}
            for plan, cfg in SAAS_PLANES_SOLO.items()
        ]
    else:
        planes_disponibles = [
            {"tier": None, "plan": plan, "precio": cfg["precio"], "dias": cfg["dias"]}
            for plan, cfg in SAAS_PLANES.items()
        ]
        planes_disponibles += [
            {"tier": SaasTier.solo, "plan": plan, "precio": cfg["precio"], "dias": cfg["dias"]}
            for plan, cfg in SAAS_PLANES_SOLO.items()
        ]

    return {
        "saas_plan":          gimnasio.saas_plan,
        "saas_estado":        gimnasio.saas_estado,
        "saas_tier":          gimnasio.saas_tier,
        "saas_vence_en":      gimnasio.saas_vence_en,
        "saas_trial_hasta":   gimnasio.saas_trial_hasta,
        "dias_restantes":     max(0, dias_restantes) if dias_restantes is not None else None,
        "pago_pendiente":     pago_pendiente is not None,
        "planes_disponibles": planes_disponibles,
    }


@gym_router.post("/solicitar", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def solicitar_suscripcion(
    request:     Request,
    plan:        SaasPlan            = Form(...),
    referencia:  str                 = Form(...),   # número de transferencia bancaria
    notas:       Optional[str]       = Form(None),
    tier:        Optional[SaasTier]  = Form(None),  # None = renovación, sin cambio de tier
    comprobante: UploadFile          = File(...),
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(require_admin),
):
    """
    El gym admin notifica que realizó una transferencia bancaria.
    Crea un registro pagos_saas en estado 'pendiente'. El comprobante es
    obligatorio (a diferencia de PagoMembresia, acá no hay ningún caso de
    "pago en efectivo" que lo vuelva innecesario — todo pago SaaS es
    transferencia) para que el platform admin pueda verificarlo antes de
    confirmar. Un solo pago pendiente por gym a la vez.

    `tier`, si viene, es un pedido de cambio de tier junto con el pago — se
    guarda en tier_solicitado y se aplica a Gimnasio.saas_tier recién cuando
    se confirma el pago (confirmar_pago), nunca acá.
    """
    if plan == SaasPlan.trial:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede solicitar el plan trial.",
        )

    if tier is not None and tier not in TIERS_AUTOSERVICIO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El tier '{tier.value}' no está disponible por autoservicio.",
        )

    if tier == SaasTier.solo and plan == SaasPlan.trimestral:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El plan Solo no está disponible en facturación trimestral.",
        )

    ya_pendiente = db.query(PagoSaas).filter(
        PagoSaas.gym_id == usuario.gym_id,
        PagoSaas.estado == EstadoPagoSaas.pendiente,
    ).first()
    if ya_pendiente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes un pago pendiente de confirmación. "
                   "Espera a que el equipo lo procese.",
        )

    referencia = sanitizar(referencia)
    notas      = sanitizar(notas)

    comprobante_url = guardar_imagen("comprobantes", str(usuario.gym_id), comprobante)

    cfg   = SAAS_PLANES_SOLO[plan.value] if tier == SaasTier.solo else SAAS_PLANES[plan.value]
    pago  = PagoSaas(
        gym_id          = usuario.gym_id,
        plan            = plan,
        monto           = cfg["precio"],
        metodo          = MetodoPago.transferencia,
        referencia      = referencia,
        notas           = notas,
        comprobante_url = comprobante_url,
        tier_solicitado = tier,
    )
    db.add(pago)

    try:
        db.commit()
    except Exception:
        borrar_archivo(comprobante_url)
        raise

    db.refresh(pago)
    return {
        "id":              pago.id,
        "plan":            pago.plan,
        "monto":           pago.monto,
        "referencia":      pago.referencia,
        "comprobante_url": pago.comprobante_url,
        "tier_solicitado": pago.tier_solicitado,
        "estado":          pago.estado,
        "mensaje":         "Solicitud registrada. El equipo confirmará tu pago en 1-2 días hábiles.",
    }


@gym_router.get("/historial")
@limiter.limit("30/minute")
def historial_suscripcion(
    request: Request,
    db:      Session       = Depends(get_db_tenant),
    usuario: UsuarioActual = Depends(get_usuario_actual),
):
    """Pagos SaaS pasados del gimnasio (todos los estados), más recientes primero."""
    pagos = (
        db.query(PagoSaas)
        .filter(PagoSaas.gym_id == usuario.gym_id)
        .order_by(PagoSaas.solicitado_en.desc())
        .all()
    )
    return [
        {
            "id":               p.id,
            "plan":             p.plan,
            "monto":            p.monto,
            "referencia":       p.referencia,
            "notas":            p.notas,
            "comprobante_url":  p.comprobante_url,
            "tier_solicitado":  p.tier_solicitado,
            "estado":           p.estado,
            "razon_rechazo":    p.razon_rechazo,
            "solicitado_en":    p.solicitado_en,
            "confirmado_en":    p.confirmado_en,
            "confirmado_por":   p.confirmado_por,
        }
        for p in pagos
    ]


# ── Endpoints del superadmin de la plataforma ─────────────────────────────────

@admin_router.get("/", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def listar_gyms_suscripciones(request: Request, db: Session = Depends(get_db_platform)):
    """Lista todos los gyms con su estado de suscripción."""
    gyms = db.query(Gimnasio).order_by(Gimnasio.saas_estado, Gimnasio.nombre).all()
    hoy  = date.today()
    return [
        {
            "id":               str(g.id),
            "nombre":           g.nombre,
            "slug":             g.slug,
            "email":            g.email,
            "saas_plan":        g.saas_plan,
            "saas_estado":      calcular_saas_estado(g, hoy),
            "saas_tier":        g.saas_tier,
            "saas_vence_en":    g.saas_vence_en,
            "saas_trial_hasta": g.saas_trial_hasta,
            "activo":           g.activo,
        }
        for g in gyms
    ]


@admin_router.get("/pagos-pendientes", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def listar_pagos_pendientes(request: Request, db: Session = Depends(get_db_platform)):
    """Lista todos los pagos pendientes de confirmación."""
    pagos = (
        db.query(PagoSaas)
        .options(joinedload(PagoSaas.gimnasio))
        .filter(PagoSaas.estado == EstadoPagoSaas.pendiente)
        .order_by(PagoSaas.solicitado_en)
        .all()
    )
    return [
        {
            "id":            p.id,
            "gym_id":        str(p.gym_id),
            "gym_nombre":    p.gimnasio.nombre if p.gimnasio else "(gimnasio eliminado)",
            "plan":             p.plan,
            "monto":            p.monto,
            "referencia":       p.referencia,
            "notas":            p.notas,
            "comprobante_url":  p.comprobante_url,
            "tier_solicitado":  p.tier_solicitado,
            "solicitado_en":    p.solicitado_en,
        }
        for p in pagos
    ]


@admin_router.post("/{gym_id}/confirmar", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def confirmar_pago(
    request: Request,
    gym_id: UUID,
    datos:  ConfirmarPagoIn,
    db:     Session = Depends(get_db_platform_admin),
):
    """
    Confirma el pago de una suscripción.
    Extiende saas_vence_en desde la fecha de vencimiento actual (o hoy si está vencido).
    Si el pago llevaba un tier_solicitado (autoservicio, ver solicitar_suscripcion),
    también aplica ese cambio a Gimnasio.saas_tier — recién acá, no antes.
    """
    pago = db.query(PagoSaas).filter(
        PagoSaas.id     == datos.pago_saas_id,
        PagoSaas.gym_id == gym_id,
        PagoSaas.estado == EstadoPagoSaas.pendiente,
    ).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago pendiente no encontrado.")

    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")

    # Extiende desde el vencimiento actual si aún está vigente, o desde hoy si venció.
    hoy  = date.today()
    base = (
        gimnasio.saas_vence_en
        if gimnasio.saas_vence_en and gimnasio.saas_vence_en >= hoy
        else hoy
    )
    nueva_fecha = _nueva_fecha_vencimiento(pago.plan, base)

    pago.estado        = EstadoPagoSaas.confirmado
    pago.confirmado_en = datetime.now(timezone.utc)
    pago.confirmado_por = datos.confirmado_por

    gimnasio.saas_plan     = pago.plan
    gimnasio.saas_estado   = SaasEstado.activa
    gimnasio.saas_vence_en = nueva_fecha
    if pago.tier_solicitado is not None:
        gimnasio.saas_tier = pago.tier_solicitado

    db.commit()
    return {
        "gym_id":        str(gym_id),
        "saas_plan":     gimnasio.saas_plan,
        "saas_estado":   gimnasio.saas_estado,
        "saas_vence_en": gimnasio.saas_vence_en,
        "saas_tier":     gimnasio.saas_tier,
    }


@admin_router.post("/{gym_id}/rechazar", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def rechazar_pago(
    request: Request,
    gym_id: UUID,
    datos:  RechazarPagoIn,
    db:     Session = Depends(get_db_platform_admin),
):
    """Rechaza un pago pendiente. El gym puede volver a solicitar."""
    pago = db.query(PagoSaas).filter(
        PagoSaas.id     == datos.pago_saas_id,
        PagoSaas.gym_id == gym_id,
        PagoSaas.estado == EstadoPagoSaas.pendiente,
    ).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago pendiente no encontrado.")

    pago.estado         = EstadoPagoSaas.rechazado
    pago.razon_rechazo  = datos.razon_rechazo
    db.commit()
    return {"gym_id": str(gym_id), "pago_id": pago.id, "estado": pago.estado}


@admin_router.post("/{gym_id}/cambiar-tier", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def cambiar_tier(
    request: Request,
    gym_id: UUID,
    datos:  CambiarTierIn,
    db:     Session = Depends(get_db_platform_admin),
):
    """
    Cambia la capacidad de staff (médicos/coaches + asistentes) del gimnasio.
    Único código que puede tocar saas_tier fuera del backfill de la
    migración 019 — antes de esto, la única forma era editar la DB a mano.
    """
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")
    if gimnasio.saas_tier == datos.tier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El gimnasio ya está en el tier '{datos.tier.value}'.",
        )

    gimnasio.saas_tier = datos.tier
    db.commit()
    return {"gym_id": str(gym_id), "saas_tier": gimnasio.saas_tier}


@admin_router.post("/{gym_id}/suspender", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def suspender_gym(
    request: Request,
    gym_id: UUID,
    datos:  SuspenderIn,
    db:     Session = Depends(get_db_platform_admin),
):
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")
    if gimnasio.saas_estado == SaasEstado.suspendida:
        raise HTTPException(status_code=409, detail="El gimnasio ya está suspendido.")

    gimnasio.saas_estado = SaasEstado.suspendida
    db.commit()
    return {"gym_id": str(gym_id), "saas_estado": gimnasio.saas_estado}


@admin_router.post("/{gym_id}/reactivar", dependencies=[Depends(require_platform_admin)])
@limiter.limit("20/minute")
def reactivar_gym(
    request: Request,
    gym_id: UUID,
    db:     Session = Depends(get_db_platform_admin),
):
    """Reactiva un gym suspendido. Si tiene saas_vence_en en el futuro, queda activa; si no, vencida."""
    gimnasio = db.query(Gimnasio).filter(Gimnasio.id == gym_id).first()
    if not gimnasio:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado.")
    if gimnasio.saas_estado != SaasEstado.suspendida:
        raise HTTPException(status_code=409, detail="El gimnasio no está suspendido.")

    hoy = date.today()
    if gimnasio.saas_vence_en and gimnasio.saas_vence_en >= hoy:
        dias = (gimnasio.saas_vence_en - hoy).days
        nuevo_estado = SaasEstado.por_vencer if dias <= 7 else SaasEstado.activa
    elif gimnasio.saas_trial_hasta and gimnasio.saas_trial_hasta >= hoy:
        nuevo_estado = SaasEstado.trial
    else:
        nuevo_estado = SaasEstado.vencida

    gimnasio.saas_estado = nuevo_estado
    db.commit()
    return {"gym_id": str(gym_id), "saas_estado": gimnasio.saas_estado}
