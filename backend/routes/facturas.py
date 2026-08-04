from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload
from models import Venta, VentaItem, Membresia, Gimnasio
from auth import get_usuario_actual, UsuarioActual, get_db_tenant
from dinero import redondear
from services.membresia_service import calcular_estado, calcular_saldo, precio_acordado_de
from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime
from html import escape
from limiter import limiter

router = APIRouter()


def _datos_gimnasio(gym_id: str, db: Session) -> dict:
    # Estos campos se interpolan sin escapar en generar_html_venta()/
    # generar_html_membresia() más abajo (el HTML se sirve crudo en /html y
    # se convierte a PDF) — se escapan acá, una sola vez, para que todo uso
    # posterior ya sea seguro.
    g = db.query(Gimnasio).filter(Gimnasio.id == gym_id).first()
    if not g:
        return {"nombre": "CrossFit SaaS", "ruc": "", "direccion": "", "telefono": ""}
    return {
        "nombre":    escape(g.nombre)    if g.nombre    else "CrossFit SaaS",
        "ruc":       escape(g.ruc)       if g.ruc       else "",
        "direccion": escape(g.direccion) if g.direccion else "",
        "telefono":  escape(g.telefono)  if g.telefono  else "",
    }


def fmt_fecha(dt) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


# ── Bloques HTML compartidos entre factura de venta y de membresía ───────────

def _estilo_pagina() -> str:
    return """
    @page { size: A4; margin: 1.2cm 1.5cm; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: Helvetica, Arial, sans-serif; font-size: 11px; color: #1f2937; }
    table { border-collapse: collapse; }
    """


def _encabezado(gym: dict, titulo_doc: str, numero: str, fecha: str,
                estado_label: str, estado_fg: str, estado_bg: str) -> str:
    tel_gym = f"<br/>{gym['telefono']}" if gym["telefono"] else ""
    dir_gym = f"<br/>{gym['direccion']}" if gym["direccion"] else ""
    return f"""
  <table width="100%" style="border-bottom:2px solid #111;padding-bottom:10px;margin-bottom:12px;">
    <tr>
      <td style="vertical-align:top;">
        <div style="font-size:17px;font-weight:bold;color:#111;">{gym["nombre"]}</div>
        <div style="font-size:10px;color:#6b7280;margin-top:2px;">{dir_gym}{tel_gym}</div>
      </td>
      <td style="text-align:right;vertical-align:top;">
        <div style="font-size:20px;font-weight:bold;color:#111;letter-spacing:2px;">{titulo_doc}</div>
        <div style="font-size:13px;font-weight:bold;color:#374151;margin-top:2px;">N.º {numero}</div>
        <div style="font-size:10px;color:#6b7280;">{fecha}</div>
        <div style="margin-top:4px;">
          <span style="display:inline-block;padding:2px 8px;border-radius:10px;
            font-size:10px;font-weight:bold;color:{estado_fg};background:{estado_bg};">{estado_label}</span>
        </div>
      </td>
    </tr>
  </table>
"""


def _bloque_emisor_cliente(gym: dict, cliente_nombre: str, cliente_extra_html: str) -> str:
    tel_gym = f"<br/>{gym['telefono']}" if gym["telefono"] else ""
    dir_gym = f"<br/>{gym['direccion']}" if gym["direccion"] else ""
    ruc_gym = f"RUC: {gym['ruc']}<br/>" if gym["ruc"] else ""
    return f"""
  <table width="100%" style="margin-bottom:12px;">
    <tr>
      <td width="48%" style="vertical-align:top;background:#f9fafb;border:1px solid #e5e7eb;padding:9px;border-radius:4px;">
        <div style="font-size:9px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;color:#9ca3af;margin-bottom:4px;">Emisor</div>
        <div style="font-size:12px;font-weight:bold;color:#111;margin-bottom:2px;">{gym["nombre"]}</div>
        <div style="font-size:10px;color:#6b7280;line-height:1.6;">{ruc_gym}{dir_gym}{tel_gym}</div>
      </td>
      <td width="4%"></td>
      <td width="48%" style="vertical-align:top;background:#f9fafb;border:1px solid #e5e7eb;padding:9px;border-radius:4px;">
        <div style="font-size:9px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;color:#9ca3af;margin-bottom:4px;">Cliente / Receptor</div>
        <div style="font-size:12px;font-weight:bold;color:#111;margin-bottom:2px;">{cliente_nombre}</div>
        <div style="font-size:10px;color:#6b7280;line-height:1.6;">{cliente_extra_html}</div>
      </td>
    </tr>
  </table>
"""


def _pie_pagina() -> str:
    return f"""
  <div style="text-align:center;font-size:9px;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:8px;margin-top:6px;">
    Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}
  </div>
"""


def _envolver_documento(cuerpo: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <style>{_estilo_pagina()}</style>
</head>
<body>
{cuerpo}
</body>
</html>"""


# ── Factura de venta (POS) ────────────────────────────────────────────────────

_ESTADO_VENTA_MAP = {
    "pagada":    ("Pagada",    "#16a34a", "#dcfce7"),
    "abono":     ("Abono",     "#a16207", "#fef9c3"),
    "cancelada": ("Cancelada", "#b91c1c", "#fee2e2"),
}


def generar_html_venta(venta: Venta, gym: dict) -> str:
    miembro      = venta.miembro
    items        = venta.items
    pagos        = venta.pagos or []
    total_pagado = redondear(sum(p.monto for p in pagos))
    saldo        = redondear(venta.total - total_pagado)

    raw = venta.estado.value if hasattr(venta.estado, "value") else str(venta.estado)
    estado_label, estado_fg, estado_bg = _ESTADO_VENTA_MAP.get(raw, ("—", "#6b7280", "#f3f4f6"))

    num_factura = f"V-{venta.id:05d}"
    iva_pct     = venta.porcentaje_iva or 0

    filas = ""
    for i, item in enumerate(items, 1):
        nombre = escape(item.producto.nombre) if item.producto else escape(item.descripcion_libre or "Costo extra")
        bg = "#f9fafb" if i % 2 == 0 else "#fff"
        filas += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:5px 8px;text-align:center;border-bottom:1px solid #e5e7eb;">{i}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e5e7eb;">{nombre}</td>'
            f'<td style="padding:5px 8px;text-align:center;border-bottom:1px solid #e5e7eb;">{item.cantidad}</td>'
            f'<td style="padding:5px 8px;text-align:right;border-bottom:1px solid #e5e7eb;">${item.precio_unitario:.2f}</td>'
            f'<td style="padding:5px 8px;text-align:right;border-bottom:1px solid #e5e7eb;">${item.subtotal:.2f}</td>'
            f'</tr>'
        )

    cliente_nombre = escape(f"{miembro.nombre} {miembro.apellido}") if miembro else "Consumidor Final"
    cedula_row     = f"Cédula: {escape(miembro.cedula)}<br/>"   if miembro and miembro.cedula   else ""
    tel_row        = f"Tel: {escape(miembro.telefono)}<br/>"    if miembro and miembro.telefono else ""

    pagado_row = (
        f'<tr><td style="padding:4px 0;color:#15803d;font-weight:bold;">Pagado</td>'
        f'<td style="text-align:right;padding:4px 0;color:#15803d;font-weight:bold;">${total_pagado:.2f}</td></tr>'
        if total_pagado > 0 else ""
    )
    saldo_row = (
        f'<tr><td style="padding:4px 0;color:#b91c1c;font-weight:bold;">Saldo pendiente</td>'
        f'<td style="text-align:right;padding:4px 0;color:#b91c1c;font-weight:bold;">${saldo:.2f}</td></tr>'
        if saldo > 0.01 else ""
    )
    notas_bloque = (
        f'<p style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:4px;'
        f'padding:8px;font-size:10px;color:#6b7280;margin-bottom:10px;">'
        f'<strong style="display:block;font-size:9px;text-transform:uppercase;'
        f'letter-spacing:1px;color:#9ca3af;margin-bottom:3px;">Notas</strong>'
        f'{escape(venta.notas)}</p>'
        if venta.notas else ""
    )

    cuerpo = f"""
  {_encabezado(gym, "FACTURA", num_factura, fmt_fecha(venta.creado_en), estado_label, estado_fg, estado_bg)}
  {_bloque_emisor_cliente(gym, cliente_nombre, f"{cedula_row}{tel_row}")}

  <table width="100%" style="margin-bottom:12px;">
    <thead>
      <tr style="background:#111;color:#fff;">
        <th style="width:32px;padding:6px 8px;text-align:center;font-size:10px;">#</th>
        <th style="padding:6px 8px;text-align:left;font-size:10px;">Descripción</th>
        <th style="width:52px;padding:6px 8px;text-align:center;font-size:10px;">Cant.</th>
        <th style="width:85px;padding:6px 8px;text-align:right;font-size:10px;">P. Unit.</th>
        <th style="width:85px;padding:6px 8px;text-align:right;font-size:10px;">Subtotal</th>
      </tr>
    </thead>
    <tbody>{filas}</tbody>
  </table>

  <table width="100%" style="margin-bottom:12px;">
    <tr>
      <td width="55%"></td>
      <td width="45%">
        <table width="100%">
          <tr>
            <td style="padding:4px 0;border-bottom:1px solid #e5e7eb;">Subtotal</td>
            <td style="text-align:right;padding:4px 0;border-bottom:1px solid #e5e7eb;">${venta.subtotal:.2f}</td>
          </tr>
          <tr>
            <td style="padding:4px 0;border-bottom:1px solid #e5e7eb;">IVA ({iva_pct:.0f}%)</td>
            <td style="text-align:right;padding:4px 0;border-bottom:1px solid #e5e7eb;">${venta.monto_iva:.2f}</td>
          </tr>
          <tr>
            <td style="padding:6px 0;border-top:2px solid #111;border-bottom:2px solid #111;font-size:14px;font-weight:bold;">TOTAL</td>
            <td style="text-align:right;padding:6px 0;border-top:2px solid #111;border-bottom:2px solid #111;font-size:14px;font-weight:bold;">${venta.total:.2f}</td>
          </tr>
          {pagado_row}{saldo_row}
        </table>
      </td>
    </tr>
  </table>

  {notas_bloque}
  {_pie_pagina()}
"""
    return _envolver_documento(cuerpo)


# ── Factura de membresía ──────────────────────────────────────────────────────

_ESTADO_MEMBRESIA_MAP = {
    "activa":         ("Activa",         "#16a34a", "#dcfce7"),
    "por_vencer":     ("Por vencer",     "#a16207", "#fef9c3"),
    "critica":        ("Crítica",        "#c2410c", "#ffedd5"),
    "vencida":        ("Vencida",        "#6b7280", "#f3f4f6"),
    "pendiente_pago": ("Pendiente pago", "#b91c1c", "#fee2e2"),
    "cancelada":      ("Cancelada",      "#6b7280", "#f3f4f6"),
}


def generar_html_membresia(membresia: Membresia, saldo, gym: dict) -> str:
    miembro = membresia.miembro
    plan    = membresia.plan
    pagos   = sorted(membresia.pagos, key=lambda p: p.fecha)

    precio_acordado = precio_acordado_de(membresia)
    total_pagado    = redondear(precio_acordado - saldo)

    estado = calcular_estado(membresia, saldo)
    raw    = estado.value if hasattr(estado, "value") else str(estado)
    estado_label, estado_fg, estado_bg = _ESTADO_MEMBRESIA_MAP.get(raw, ("—", "#6b7280", "#f3f4f6"))

    num_factura = f"M-{membresia.id:05d}"

    plan_nombre = escape(plan.nombre) if plan else f"Membresía #{membresia.id}"
    fila = (
        f'<tr style="background:#fff">'
        f'<td style="padding:5px 8px;text-align:center;border-bottom:1px solid #e5e7eb;">1</td>'
        f'<td style="padding:5px 8px;border-bottom:1px solid #e5e7eb;">Membresía: {plan_nombre}</td>'
        f'<td style="padding:5px 8px;text-align:center;border-bottom:1px solid #e5e7eb;">1</td>'
        f'<td style="padding:5px 8px;text-align:right;border-bottom:1px solid #e5e7eb;">${precio_acordado:.2f}</td>'
        f'<td style="padding:5px 8px;text-align:right;border-bottom:1px solid #e5e7eb;">${precio_acordado:.2f}</td>'
        f'</tr>'
    )

    cliente_nombre = escape(f"{miembro.nombre} {miembro.apellido}") if miembro else "—"
    cedula_row     = f"Cédula: {escape(miembro.cedula)}<br/>"   if miembro and miembro.cedula   else ""
    tel_row        = f"Tel: {escape(miembro.telefono)}<br/>"    if miembro and miembro.telefono else ""

    pagado_row = (
        f'<tr><td style="padding:4px 0;color:#15803d;font-weight:bold;">Pagado</td>'
        f'<td style="text-align:right;padding:4px 0;color:#15803d;font-weight:bold;">${total_pagado:.2f}</td></tr>'
        if total_pagado > 0 else ""
    )
    saldo_row = (
        f'<tr><td style="padding:4px 0;color:#b91c1c;font-weight:bold;">Saldo pendiente</td>'
        f'<td style="text-align:right;padding:4px 0;color:#b91c1c;font-weight:bold;">${saldo:.2f}</td></tr>'
        if saldo > 0.01 else ""
    )

    filas_pagos = ""
    for i, p in enumerate(pagos, 1):
        bg = "#f9fafb" if i % 2 == 0 else "#fff"
        metodo = p.metodo.value if hasattr(p.metodo, "value") else str(p.metodo)
        filas_pagos += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;">{fmt_fecha(p.fecha)}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;">{escape(metodo)}</td>'
            f'<td style="padding:4px 8px;text-align:right;border-bottom:1px solid #e5e7eb;">${p.monto:.2f}</td>'
            f'</tr>'
        )
    historial_pagos = (
        f"""
  <table width="100%" style="margin-bottom:12px;">
    <thead>
      <tr style="background:#111;color:#fff;">
        <th style="padding:5px 8px;text-align:left;font-size:9px;">Fecha</th>
        <th style="padding:5px 8px;text-align:left;font-size:9px;">Método</th>
        <th style="padding:5px 8px;text-align:right;font-size:9px;">Monto</th>
      </tr>
    </thead>
    <tbody>{filas_pagos}</tbody>
  </table>
"""
        if pagos else ""
    )

    notas_bloque = (
        f'<p style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:4px;'
        f'padding:8px;font-size:10px;color:#6b7280;margin-bottom:10px;">'
        f'<strong style="display:block;font-size:9px;text-transform:uppercase;'
        f'letter-spacing:1px;color:#9ca3af;margin-bottom:3px;">Notas</strong>'
        f'{escape(membresia.notas)}</p>'
        if membresia.notas else ""
    )

    cuerpo = f"""
  {_encabezado(gym, "FACTURA", num_factura, fmt_fecha(membresia.creado_en), estado_label, estado_fg, estado_bg)}
  {_bloque_emisor_cliente(gym, cliente_nombre, f"{cedula_row}{tel_row}")}

  <table width="100%" style="margin-bottom:12px;">
    <thead>
      <tr style="background:#111;color:#fff;">
        <th style="width:32px;padding:6px 8px;text-align:center;font-size:10px;">#</th>
        <th style="padding:6px 8px;text-align:left;font-size:10px;">Descripción</th>
        <th style="width:52px;padding:6px 8px;text-align:center;font-size:10px;">Cant.</th>
        <th style="width:85px;padding:6px 8px;text-align:right;font-size:10px;">P. Unit.</th>
        <th style="width:85px;padding:6px 8px;text-align:right;font-size:10px;">Subtotal</th>
      </tr>
    </thead>
    <tbody>{fila}</tbody>
  </table>

  <table width="100%" style="margin-bottom:12px;">
    <tr>
      <td width="55%"></td>
      <td width="45%">
        <table width="100%">
          <tr>
            <td style="padding:6px 0;border-top:2px solid #111;border-bottom:2px solid #111;font-size:14px;font-weight:bold;">TOTAL</td>
            <td style="text-align:right;padding:6px 0;border-top:2px solid #111;border-bottom:2px solid #111;font-size:14px;font-weight:bold;">${precio_acordado:.2f}</td>
          </tr>
          {pagado_row}{saldo_row}
        </table>
      </td>
    </tr>
  </table>

  {historial_pagos}
  {notas_bloque}
  {_pie_pagina()}
"""
    return _envolver_documento(cuerpo)


# ── PDF ────────────────────────────────────────────────────────────────────────

def _html_a_pdf(html: str) -> bytes:
    buf = BytesIO()
    result = pisa.CreatePDF(html, dest=buf)
    if result.err:
        raise HTTPException(status_code=500, detail="Error al generar el PDF.")
    return buf.getvalue()


def _cargar_venta(venta_id: int, gym_id: str, db: Session) -> Venta:
    v = (
        db.query(Venta)
        .options(
            joinedload(Venta.miembro),
            joinedload(Venta.items).joinedload(VentaItem.producto),
            joinedload(Venta.pagos),
        )
        .filter(Venta.id == venta_id, Venta.gym_id == gym_id)
        .first()
    )
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    return v


def _cargar_membresia(membresia_id: int, gym_id: str, db: Session) -> Membresia:
    m = (
        db.query(Membresia)
        .options(
            joinedload(Membresia.miembro),
            joinedload(Membresia.plan),
            joinedload(Membresia.pagos),
        )
        .filter(Membresia.id == membresia_id, Membresia.gym_id == gym_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")
    return m


# ── Rutas: factura de venta ───────────────────────────────────────────────────

@router.get("/venta/{venta_id}/pdf")
@limiter.limit("20/minute")
def descargar_pdf_venta(
    request:  Request,
    venta_id: int,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = _cargar_venta(venta_id, usuario.gym_id, db)
    gym   = _datos_gimnasio(usuario.gym_id, db)
    pdf   = _html_a_pdf(generar_html_venta(venta, gym))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="factura_V-{venta.id:05d}.pdf"'},
    )


@router.get("/venta/{venta_id}/html", response_class=HTMLResponse)
def previsualizar_html_venta(
    venta_id: int,
    db:       Session       = Depends(get_db_tenant),
    usuario:  UsuarioActual = Depends(get_usuario_actual),
):
    venta = _cargar_venta(venta_id, usuario.gym_id, db)
    gym   = _datos_gimnasio(usuario.gym_id, db)
    return HTMLResponse(content=generar_html_venta(venta, gym))


# ── Rutas: factura de membresía ───────────────────────────────────────────────

@router.get("/membresia/{membresia_id}/pdf")
@limiter.limit("20/minute")
def descargar_pdf_membresia(
    request:      Request,
    membresia_id: int,
    db:           Session       = Depends(get_db_tenant),
    usuario:      UsuarioActual = Depends(get_usuario_actual),
):
    membresia = _cargar_membresia(membresia_id, usuario.gym_id, db)
    saldo     = calcular_saldo(membresia, db)
    gym       = _datos_gimnasio(usuario.gym_id, db)
    pdf       = _html_a_pdf(generar_html_membresia(membresia, saldo, gym))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="factura_M-{membresia.id:05d}.pdf"'},
    )


@router.get("/membresia/{membresia_id}/html", response_class=HTMLResponse)
def previsualizar_html_membresia(
    membresia_id: int,
    db:           Session       = Depends(get_db_tenant),
    usuario:      UsuarioActual = Depends(get_usuario_actual),
):
    membresia = _cargar_membresia(membresia_id, usuario.gym_id, db)
    saldo     = calcular_saldo(membresia, db)
    gym       = _datos_gimnasio(usuario.gym_id, db)
    return HTMLResponse(content=generar_html_membresia(membresia, saldo, gym))
