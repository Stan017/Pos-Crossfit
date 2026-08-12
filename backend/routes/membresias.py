from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, File, UploadFile, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date, timedelta

from models import Membresia, Miembro, Plan, EstadoMembresia, MetodoPago, PagoMembresia, Asistencia
from auth import get_usuario_actual, require_admin, UsuarioActual, get_db_tenant
from dinero import a_decimal, redondear
from storage import guardar_imagen, borrar_archivo
from security import sanitizar
from limiter import limiter
from services.membresia_service import (
    DIAS_POR_VENCER, ESTADOS_VIGENTES,
    calcular_estado, calcular_saldo, batch_saldos, precio_acordado_de,
)

router = APIRouter()


# ── Helpers de estado ─────────────────────────────────────────────────────────

def _sincronizar_estado(membresia: Membresia, saldo: float) -> None:
    """Actualiza el campo estado almacenado para mantenerlo en sincronía con la realidad."""
    membresia.estado = calcular_estado(membresia, saldo)


# ── Schemas ───────────────────────────────────────────────────────────────────

# Los tres endpoints que crean un PagoMembresia (crear, renovar, registrar
# pago) reciben Form(...) en vez de un body JSON con estos campos: necesitan
# aceptar también un archivo (comprobante), y FastAPI no permite mezclar un
# body JSON con UploadFile en el mismo request — todo pasa a ser multipart.
#
# crear_membresia y renovar_membresia comparten los mismos 6 campos (todo
# excepto miembro_id, que solo aplica a crear) — form_membresia() los junta
# una sola vez en vez de repetir el mismo bloque de Form(...) en las dos rutas.

class DatosMembresiaForm(BaseModel):
    plan_id:         int
    fecha_inicio:    date
    precio_pagado:   float           = Field(ge=0)
    metodo_pago:     MetodoPago
    precio_acordado: Optional[float] = Field(default=None, ge=0)
    notas:           Optional[str]   = None

    @field_validator("notas", mode="before")
    @classmethod
    def limpiar_texto(cls, v):
        return sanitizar(v)


# 90 como tope absoluto (no relativo a clases_total del plan): así lo pidió
# el usuario — es un límite de cordura contra un typo (ej. 9999), no una
# regla de negocio atada al plan. A propósito NO se valida contra
# clases_total: un admin puede querer dejar constancia de que un paciente
# ya venía con más sesiones previas de las que el plan actual define, sin
# que el sistema se lo impida.
class AsistidasInput(BaseModel):
    clases_usadas: int = Field(ge=0, le=90)


def form_membresia(
    plan_id:         int               = Form(...),
    fecha_inicio:    date              = Form(...),
    precio_pagado:   float             = Form(...),
    metodo_pago:     MetodoPago        = Form(...),
    precio_acordado: Optional[float]   = Form(None),  # si None, usa el precio del plan
    notas:           Optional[str]     = Form(None),
) -> DatosMembresiaForm:
    # Validado acá, antes de construir DatosMembresiaForm a mano: un
    # ValidationError de pydantic lanzado dentro de un Depends() no lo
    # traduce FastAPI a un 422 limpio (no es un RequestValidationError, cae
    # al handler genérico de main.py como 500) — por eso el chequeo explícito
    # en vez de confiar solo en Field(ge=0) del modelo.
    if precio_pagado < 0:
        raise HTTPException(status_code=422, detail="precio_pagado no puede ser negativo.")
    if precio_acordado is not None and precio_acordado < 0:
        raise HTTPException(status_code=422, detail="precio_acordado no puede ser negativo.")
    return DatosMembresiaForm(
        plan_id=plan_id, fecha_inicio=fecha_inicio, precio_pagado=precio_pagado,
        metodo_pago=metodo_pago, precio_acordado=precio_acordado, notas=notas,
    )


# ── Serializer ────────────────────────────────────────────────────────────────

def _serializar(m: Membresia, saldo: float = 0.0) -> dict:
    return {
        "id":            m.id,
        "miembro_id":    m.miembro_id,
        "miembro": {
            "id":       m.miembro.id,
            "nombre":   m.miembro.nombre,
            "apellido": m.miembro.apellido,
        } if m.miembro else None,
        "plan_id": m.plan_id,
        "plan": {
            "id":     m.plan.id,
            "nombre": m.plan.nombre,
            "tipo":   m.plan.tipo,
            "precio": m.plan.precio,
        } if m.plan else None,
        "fecha_inicio":    m.fecha_inicio,
        "fecha_fin":       m.fecha_fin,
        "precio_pagado":   m.precio_pagado,
        "precio_acordado": m.precio_acordado,
        "metodo_pago":     m.metodo_pago,
        "clases_total":    m.clases_total,
        "clases_usadas":   m.clases_usadas,
        "estado":          calcular_estado(m, saldo),
        "saldo":           saldo,
        "notas":           m.notas,
        "creado_en":       m.creado_en,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def listar_membresias(
    estado:     Optional[str] = Query(None),
    miembro_id: Optional[int] = Query(None),
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    query = (
        db.query(Membresia)
        .options(joinedload(Membresia.miembro), joinedload(Membresia.plan))
        .filter(Membresia.gym_id == usuario.gym_id)
    )
    if miembro_id:
        query = query.filter(Membresia.miembro_id == miembro_id)

    membresias = query.order_by(Membresia.creado_en.desc()).all()
    saldos = batch_saldos(membresias, db)
    resultado = [_serializar(m, saldos.get(m.id, a_decimal(0))) for m in membresias]

    # Filtra por el estado ya recalculado (no por la columna persistida):
    # una membresía que venció sin que nadie la tocara sigue mostrando el
    # último estado escrito en DB, que puede estar obsoleto.
    if estado:
        resultado = [r for r in resultado if r["estado"] == estado]
    return resultado


@router.get("/alertas")
def obtener_alertas(
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    hoy    = date.today()
    limite = hoy + timedelta(days=DIAS_POR_VENCER)

    # Se recalcula el estado de cada membresía en vez de confiar en la
    # columna persistida: esta solo se actualiza en escrituras (crear,
    # renovar, pagar), así que una membresía que vence sin que nadie la
    # toque se queda mostrando el último estado guardado.
    candidatas = db.query(Membresia).filter(
        Membresia.gym_id == usuario.gym_id,
        Membresia.estado != EstadoMembresia.cancelada,
    ).all()
    saldos = batch_saldos(candidatas, db)

    criticas         = []
    por_vencer       = []
    pendientes_pago  = []

    for m in candidatas:
        saldo  = saldos.get(m.id, a_decimal(0))
        estado = calcular_estado(m, saldo)

        if estado == EstadoMembresia.pendiente_pago:
            pendientes_pago.append({
                "membresia_id": m.id,
                "miembro_id":   m.miembro_id,
                "tipo":         "deuda",
            })
            continue

        if estado == EstadoMembresia.vencida:
            continue  # ya venció, no es una alerta de "por vencer"

        if m.fecha_fin is not None:
            dias = (m.fecha_fin - hoy).days
            if m.fecha_fin > limite:
                continue
            entrada = {
                "membresia_id":   m.id,
                "miembro_id":     m.miembro_id,
                "tipo":           "tiempo",
                "fecha_fin":      m.fecha_fin,
                "dias_restantes": dias,
            }
            if estado == EstadoMembresia.critica:
                criticas.append(entrada)
            elif estado == EstadoMembresia.por_vencer:
                por_vencer.append(entrada)
        elif estado == EstadoMembresia.critica and m.clases_total is not None:
            clases_disponibles = m.clases_total - m.clases_usadas
            criticas.append({
                "membresia_id":       m.id,
                "miembro_id":         m.miembro_id,
                "tipo":               "clases",
                "clases_disponibles": clases_disponibles,
                "clases_total":       m.clases_total,
            })

    return {
        "criticas":        sorted(
            [x for x in criticas if x.get("tipo") == "tiempo"],
            key=lambda x: x["dias_restantes"],
        ) + [x for x in criticas if x.get("tipo") == "clases"],
        "por_vencer":      sorted(por_vencer, key=lambda x: x["dias_restantes"]),
        "pendientes_pago": pendientes_pago,
        "total":           len(criticas) + len(por_vencer) + len(pendientes_pago),
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def crear_membresia(
    request:     Request,
    miembro_id:  int                   = Form(...),
    datos:       DatosMembresiaForm    = Depends(form_membresia),
    comprobante: Optional[UploadFile]  = File(None),
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    # with_for_update() sobre el miembro serializa creaciones de membresía
    # concurrentes para el mismo miembro_id: no hay fila de Membresia que
    # lockear todavía (puede que no exista ninguna vigente), así que se
    # lockea al padre para forzar que la segunda transacción espere y
    # vuelva a ver la membresía recién creada por la primera.
    miembro = db.query(Miembro).filter(
        Miembro.id     == miembro_id,
        Miembro.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not miembro:
        raise HTTPException(status_code=404, detail="Miembro no encontrado.")

    # Verificar que no tenga membresía vigente (activa, pendiente de pago, por vencer, crítica)
    vigente = db.query(Membresia).filter(
        Membresia.gym_id     == usuario.gym_id,
        Membresia.miembro_id == miembro_id,
        Membresia.estado.in_(ESTADOS_VIGENTES),
    ).first()
    if vigente:
        if vigente.fecha_fin is not None and vigente.fecha_fin < datos.fecha_inicio:
            vigente.estado = EstadoMembresia.vencida
            db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El miembro ya tiene una membresía vigente."
            )

    plan = db.query(Plan).filter(
        Plan.id     == datos.plan_id,
        Plan.gym_id == usuario.gym_id,
        Plan.activo == True,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")

    fecha_fin    = None
    clases_total = None
    if plan.tipo == "tiempo":
        fecha_fin = datos.fecha_inicio + timedelta(days=plan.duracion_dias)
    else:
        clases_total = plan.clases_total

    # a_decimal() acá, no solo al escribir: calcular_saldo() lee estos
    # atributos del mismo objeto en memoria antes del db.refresh(), así que
    # si quedaran como float (asignación directa) la resta con Decimal revienta.
    precio_acordado_dec = a_decimal(datos.precio_acordado if datos.precio_acordado is not None else plan.precio)

    membresia = Membresia(
        gym_id          = usuario.gym_id,
        miembro_id      = miembro_id,
        plan_id         = datos.plan_id,
        fecha_inicio    = datos.fecha_inicio,
        fecha_fin       = fecha_fin,
        precio_pagado   = a_decimal(datos.precio_pagado),
        precio_acordado = precio_acordado_dec,
        metodo_pago     = datos.metodo_pago,
        clases_total    = clases_total,
        clases_usadas   = 0,
        notas           = datos.notas,
        creado_por      = usuario.user_id,
    )
    db.add(membresia)
    db.flush()

    comprobante_url = None
    if datos.precio_pagado > 0:
        comprobante_url = guardar_imagen("comprobantes", str(usuario.gym_id), comprobante) if comprobante else None
        pago = PagoMembresia(
            gym_id          = usuario.gym_id,
            membresia_id    = membresia.id,
            monto           = a_decimal(datos.precio_pagado),
            metodo          = datos.metodo_pago,
            registrado_por  = usuario.user_id,
            comprobante_url = comprobante_url,
        )
        db.add(pago)

    try:
        db.flush()
        saldo = calcular_saldo(membresia, db)
        _sincronizar_estado(membresia, saldo)
        db.commit()
    except Exception:
        if comprobante_url:
            borrar_archivo(comprobante_url)
        raise

    db.refresh(membresia)
    return _serializar(membresia, saldo)


@router.patch("/{membresia_id}/renovar", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def renovar_membresia(
    request:      Request,
    membresia_id: int,
    datos:       DatosMembresiaForm    = Depends(form_membresia),
    comprobante: Optional[UploadFile]  = File(None),
    db:      Session        = Depends(get_db_tenant),
    usuario: UsuarioActual  = Depends(get_usuario_actual),
):
    """Marca la membresía actual como vencida y crea una nueva."""
    # with_for_update() serializa dos renovaciones concurrentes de la misma
    # membresía (doble clic, retry de red): la segunda espera a que la
    # primera confirme antes de leer la fila.
    actual = db.query(Membresia).filter(
        Membresia.id     == membresia_id,
        Membresia.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not actual:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    if actual.estado == EstadoMembresia.cancelada:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede renovar una membresía cancelada."
        )

    # Si la primera transacción ya renovó mientras esta esperaba el lock,
    # va a existir una membresía vigente distinta de "actual" para el mismo
    # miembro — sin este chequeo, la segunda request crearía una segunda
    # membresía nueva (y un segundo cobro) por la misma renovación.
    ya_renovada = db.query(Membresia).filter(
        Membresia.gym_id     == usuario.gym_id,
        Membresia.miembro_id == actual.miembro_id,
        Membresia.id         != actual.id,
        Membresia.estado.in_(ESTADOS_VIGENTES),
    ).first()
    if ya_renovada:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta membresía ya fue renovada.",
        )

    plan = db.query(Plan).filter(
        Plan.id     == datos.plan_id,
        Plan.gym_id == usuario.gym_id,
        Plan.activo == True,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")

    actual.estado = EstadoMembresia.vencida

    fecha_fin    = None
    clases_total = None
    if plan.tipo == "tiempo":
        fecha_fin = datos.fecha_inicio + timedelta(days=plan.duracion_dias)
    else:
        clases_total = plan.clases_total

    precio_acordado_dec = a_decimal(datos.precio_acordado if datos.precio_acordado is not None else plan.precio)

    nueva = Membresia(
        gym_id          = usuario.gym_id,
        miembro_id      = actual.miembro_id,
        plan_id         = datos.plan_id,
        fecha_inicio    = datos.fecha_inicio,
        fecha_fin       = fecha_fin,
        precio_pagado   = a_decimal(datos.precio_pagado),
        precio_acordado = precio_acordado_dec,
        metodo_pago     = datos.metodo_pago,
        clases_total    = clases_total,
        clases_usadas   = 0,
        notas           = datos.notas,
        creado_por      = usuario.user_id,
    )
    db.add(nueva)
    db.flush()

    comprobante_url = None
    if datos.precio_pagado > 0:
        comprobante_url = guardar_imagen("comprobantes", str(usuario.gym_id), comprobante) if comprobante else None
        pago = PagoMembresia(
            gym_id          = usuario.gym_id,
            membresia_id    = nueva.id,
            monto           = a_decimal(datos.precio_pagado),
            metodo          = datos.metodo_pago,
            registrado_por  = usuario.user_id,
            comprobante_url = comprobante_url,
        )
        db.add(pago)

    try:
        db.flush()
        saldo = calcular_saldo(nueva, db)
        _sincronizar_estado(nueva, saldo)
        db.commit()
    except Exception:
        if comprobante_url:
            borrar_archivo(comprobante_url)
        raise

    db.refresh(nueva)
    return _serializar(nueva, saldo)


# ── Pagos de membresía ────────────────────────────────────────────────────────

def _serializar_pago(p: PagoMembresia) -> dict:
    return {
        "id": p.id, "monto": p.monto, "metodo": p.metodo, "fecha": p.fecha,
        "notas": p.notas, "comprobante_url": p.comprobante_url,
    }


@router.get("/{membresia_id}/pagos")
def listar_pagos_membresia(
    membresia_id: int,
    db:           Session        = Depends(get_db_tenant),
    usuario:      UsuarioActual  = Depends(get_usuario_actual),
):
    membresia = db.query(Membresia).filter(
        Membresia.id     == membresia_id,
        Membresia.gym_id == usuario.gym_id,
    ).first()
    if not membresia:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    pagos = (
        db.query(PagoMembresia)
        .filter(PagoMembresia.membresia_id == membresia_id)
        .order_by(PagoMembresia.fecha)
        .all()
    )
    return [_serializar_pago(p) for p in pagos]


@router.get("/historial/{miembro_id}")
def historial_pagos_miembro(
    miembro_id: int,
    db:         Session        = Depends(get_db_tenant),
    usuario:    UsuarioActual  = Depends(get_usuario_actual),
):
    """Membresías de un miembro con sus pagos ya cargados (1 query, no N+1)."""
    membresias = (
        db.query(Membresia)
        .options(joinedload(Membresia.pagos))
        .filter(
            Membresia.miembro_id == miembro_id,
            Membresia.gym_id     == usuario.gym_id,
        )
        .order_by(Membresia.creado_en.desc())
        .all()
    )
    saldos = batch_saldos(membresias, db)
    return [
        {
            **_serializar(m, saldos.get(m.id, a_decimal(0))),
            "pagos": [_serializar_pago(p) for p in sorted(m.pagos, key=lambda p: p.fecha)],
        }
        for m in membresias
    ]


@router.post("/{membresia_id}/pagos", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def registrar_pago_membresia(
    request:      Request,
    membresia_id: int,
    monto:       float                 = Form(...),
    metodo:      MetodoPago            = Form(...),
    notas:       Optional[str]         = Form(None),
    comprobante: Optional[UploadFile]  = File(None),
    db:           Session        = Depends(get_db_tenant),
    usuario:      UsuarioActual  = Depends(get_usuario_actual),
):
    # with_for_update() previene que dos pagos concurrentes lean el mismo
    # saldo antes de que ninguno confirme, lo que permitiría sobrepagar
    # la membresía (mismo criterio que registrar_abono en abonos.py)
    membresia = db.query(Membresia).filter(
        Membresia.id     == membresia_id,
        Membresia.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not membresia:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    if monto <= 0:
        raise HTTPException(status_code=422, detail="El monto debe ser mayor a 0.")

    if membresia.estado == EstadoMembresia.cancelada:
        raise HTTPException(status_code=409, detail="No se puede registrar un pago en una membresía cancelada.")

    notas = sanitizar(notas)
    saldo_actual = calcular_saldo(membresia, db)
    monto_dec    = redondear(a_decimal(monto))
    if monto_dec > saldo_actual:
        raise HTTPException(
            status_code=400,
            detail=f"El pago ({monto:.2f}) supera el saldo pendiente ({saldo_actual:.2f})."
        )

    comprobante_url = guardar_imagen("comprobantes", str(usuario.gym_id), comprobante) if comprobante else None
    pago = PagoMembresia(
        gym_id          = usuario.gym_id,
        membresia_id    = membresia_id,
        monto           = monto_dec,
        metodo          = metodo,
        notas           = notas,
        registrado_por  = usuario.user_id,
        comprobante_url = comprobante_url,
    )
    db.add(pago)

    try:
        db.flush()
        # Recompute saldo y sincronizar estado
        saldo = calcular_saldo(membresia, db)
        _sincronizar_estado(membresia, saldo)
        db.commit()
    except Exception:
        if comprobante_url:
            borrar_archivo(comprobante_url)
        raise

    db.refresh(pago)
    return {
        "id":              pago.id,
        "monto":           pago.monto,
        "metodo":          pago.metodo,
        "fecha":           pago.fecha,
        "comprobante_url": pago.comprobante_url,
        "saldo_restante":  saldo,
    }


@router.get("/{membresia_id}/saldo")
def saldo_membresia(
    membresia_id: int,
    db:           Session        = Depends(get_db_tenant),
    usuario:      UsuarioActual  = Depends(get_usuario_actual),
):
    membresia = db.query(Membresia).filter(
        Membresia.id     == membresia_id,
        Membresia.gym_id == usuario.gym_id,
    ).first()
    if not membresia:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    saldo = calcular_saldo(membresia, db)
    precio_acordado = precio_acordado_de(membresia)
    total_pagado = redondear(precio_acordado - saldo)
    return {
        "membresia_id":    membresia_id,
        "precio_acordado": precio_acordado,
        "total_pagado":    total_pagado,
        "saldo":           saldo,
    }


@router.delete("/{membresia_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_membresia(
    membresia_id: int,
    db:           Session        = Depends(get_db_tenant),
    usuario:      UsuarioActual  = Depends(get_usuario_actual),
):
    """
    Corrige una membresía mal cargada (plan equivocado, miembro equivocado,
    etc.) borrándola por completo — no un "cancelar", que dejaría la fila y
    seguiría bloqueando "el miembro ya tiene una membresía vigente" en
    crear_membresia. Cualquier staff logueado, no solo admin — mismo criterio
    que eliminar_venta_y_restaurar_stock (quien comete el error de carga es
    típicamente quien necesita poder corregirlo). A diferencia de esa ruta,
    acá sí se permite borrar con pagos ya registrados: pagos_membresia SÍ está
    en la lista de tablas auditadas en audit.py (a diferencia de pagos de venta,
    excluidos a propósito), así que borrar no hace desaparecer el rastro.
    """
    # with_for_update(of=Membresia) serializa esto contra un check-in
    # concurrente sobre la misma membresía (checkin.py también lockea la fila
    # con FOR UPDATE): sin esto, un check-in podía colarse entre el chequeo de
    # "tiene_asistencias" de abajo y el DELETE, y el DELETE terminaba chocando
    # con la FK de asistencias.membresia_id (sin cascada) — un IntegrityError
    # crudo (500) en vez del 409 limpio que esta ruta ya sabe devolver.
    # of=Membresia (no un FOR UPDATE liso): pagos es un LEFT JOIN (una
    # membresía puede no tener pagos todavía) y Postgres rechaza "FOR UPDATE"
    # sobre el lado nullable de un outer join — hay que decirle explícitamente
    # qué tabla lockear.
    membresia = (
        db.query(Membresia)
        .options(joinedload(Membresia.pagos))
        .filter(Membresia.id == membresia_id, Membresia.gym_id == usuario.gym_id)
        .with_for_update(of=Membresia)
        .first()
    )
    if not membresia:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    # Asistencia.membresia_id no tiene cascada (a propósito: un check-in ya
    # realizado es evidencia real de que el paciente/miembro asistió, no se
    # borra solo porque la membresía que lo respaldaba se está corrigiendo).
    tiene_asistencias = db.query(Asistencia.id).filter(
        Asistencia.membresia_id == membresia_id,
    ).first() is not None
    if tiene_asistencias:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: esta membresía ya tiene asistencias registradas.",
        )

    # Los archivos se borran DESPUÉS del commit, no antes: si el borrado del
    # archivo corriera primero y el commit fallara por cualquier motivo, la
    # membresía seguiría viva en la DB pero ya habría perdido su comprobante.
    comprobantes = [p.comprobante_url for p in membresia.pagos if p.comprobante_url]

    db.delete(membresia)  # cascada: membresia.pagos (PagoMembresia)
    db.commit()

    for url in comprobantes:
        borrar_archivo(url)


@router.patch("/{membresia_id}/asistencias")
def editar_asistencias(
    membresia_id: int,
    datos:        AsistidasInput,
    db:           Session        = Depends(get_db_tenant),
    usuario:      UsuarioActual  = Depends(require_admin),
):
    """
    Ajusta a mano el conteo de sesiones asistidas — pensado para el caso de
    onboarding: una clínica/box que se pasa a este sistema con un paciente/
    miembro que ya venía con sesiones previas hechas fuera del programa
    (o antes de digitalizar), así el saldo de clases restantes arranca
    correcto en vez de en 0. Solo admin, a diferencia de eliminar_membresia
    — esto no es corregir un error de carga propio, es una operación
    delicada de re-conteo. with_for_update() por el mismo motivo que
    checkin.py: dos ediciones (o una edición + un check-in) concurrentes no
    deben pisarse.
    """
    membresia = db.query(Membresia).filter(
        Membresia.id     == membresia_id,
        Membresia.gym_id == usuario.gym_id,
    ).with_for_update().first()
    if not membresia:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    if membresia.fecha_fin is not None or membresia.clases_total is None:
        raise HTTPException(
            status_code=409,
            detail="Este plan es por tiempo, no lleva conteo de sesiones asistidas.",
        )

    # calcular_estado() trata "vencida" como estado terminal y no lo recalcula
    # desde clases_usadas/clases_total — correcto cuando renovar_membresia lo
    # marcó a propósito al reemplazar esta fila por una nueva, pero incorrecto
    # cuando llegó a "vencida" solo porque checkin.py agotó las clases (que es
    # justo el caso que este endpoint existe para corregir). Distinguimos los
    # dos casos igual que ya_renovada en renovar_membresia: si existe otra
    # membresía vigente para el mismo miembro, esta fue reemplazada de verdad
    # y "vencida" se respeta tal cual; si no, se fuerza un recálculo real.
    if membresia.estado == EstadoMembresia.vencida:
        fue_reemplazada = db.query(Membresia.id).filter(
            Membresia.gym_id     == usuario.gym_id,
            Membresia.miembro_id == membresia.miembro_id,
            Membresia.id         != membresia.id,
            Membresia.estado.in_(ESTADOS_VIGENTES),
        ).first() is not None
        if not fue_reemplazada:
            membresia.estado = EstadoMembresia.activa

    membresia.clases_usadas = datos.clases_usadas
    saldo = calcular_saldo(membresia, db)
    _sincronizar_estado(membresia, saldo)
    db.commit()
    db.refresh(membresia)
    return _serializar(membresia, saldo)
