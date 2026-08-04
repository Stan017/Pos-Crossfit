"""
Fase 3 de cobertura: suscripciones.py, lado gym-admin (/estado, /solicitar,
/historial). El lado superadmin (/admin/suscripciones) usa X-Platform-Key en
vez de rol de gym — queda cubierto acá solo para el flujo del tier "solo"
(confirmar_pago aplicando tier_solicitado), no de forma exhaustiva.
"""
import io

from conftest import nuevo_client
from test_auth_rls import _registrar_gym

# 1x1 PNG válido — el mismo magic number que storage.py valida.
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415478da6360000002000155037f020000000049454e44"
    "ae426082"
)


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "susc")
    return client


def test_estado_suscripcion_recien_registrado_es_trial():
    client = _cliente_con_gym()
    r = client.get("/suscripciones/estado")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saas_estado"] == "trial"
    assert body["pago_pendiente"] is False


def test_solicitar_suscripcion_rechaza_plan_trial():
    client = _cliente_con_gym()
    r = client.post(
        "/suscripciones/solicitar",
        data={"plan": "trial", "referencia": "TX123"},
        files={"comprobante": ("comp.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 422


def test_solicitar_suscripcion_crea_pago_pendiente():
    client = _cliente_con_gym()
    r = client.post(
        "/suscripciones/solicitar",
        data={"plan": "mensual", "referencia": "TX123"},
        files={"comprobante": ("comp.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "pendiente"

    estado = client.get("/suscripciones/estado").json()
    assert estado["pago_pendiente"] is True


def test_solicitar_suscripcion_rechaza_segunda_mientras_hay_pendiente():
    client = _cliente_con_gym()
    client.post(
        "/suscripciones/solicitar",
        data={"plan": "mensual", "referencia": "TX1"},
        files={"comprobante": ("a.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    r2 = client.post(
        "/suscripciones/solicitar",
        data={"plan": "mensual", "referencia": "TX2"},
        files={"comprobante": ("b.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r2.status_code == 409, r2.text


def test_solicitar_plan_semestral_ya_es_real_no_solo_de_marketing():
    """
    Antes de la migración 037, 'semestral' se veía en la página de marketing
    (Estándar $220/semestre) pero SaasPlan nunca lo tuvo — nadie lo podía
    comprar de verdad. Esto confirma que ahora sí.
    """
    client = _cliente_con_gym()
    opciones = client.get("/suscripciones/estado").json()["planes_disponibles"]
    semestral = next(o for o in opciones if o["tier"] is None and o["plan"] == "semestral")
    assert float(semestral["precio"]) == 220.0

    r = client.post(
        "/suscripciones/solicitar",
        data={"plan": "semestral", "referencia": "TX-SEM"},
        files={"comprobante": ("c.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 201, r.text
    assert float(r.json()["monto"]) == 220.0


def test_historial_suscripcion_incluye_lo_solicitado():
    client = _cliente_con_gym()
    client.post(
        "/suscripciones/solicitar",
        data={"plan": "trimestral", "referencia": "TX1"},
        files={"comprobante": ("a.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    r = client.get("/suscripciones/historial")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["plan"] == "trimestral"


# ── Tier "solo" ($20/mes, autoservicio) ──────────────────────────────────────

ADMIN_HEADERS = {"X-Platform-Key": "test-platform-key-nunca-usar-en-produccion"}


def test_estado_ofrece_tier_solo_en_sus_tres_periodos_para_un_gym_nuevo():
    client = _cliente_con_gym()
    opciones = client.get("/suscripciones/estado").json()["planes_disponibles"]
    solo_por_plan = {o["plan"]: o for o in opciones if o["tier"] == "solo"}
    assert set(solo_por_plan) == {"mensual", "semestral", "anual"}
    assert float(solo_por_plan["mensual"]["precio"]) == 20.0
    assert float(solo_por_plan["semestral"]["precio"]) == 100.0
    assert float(solo_por_plan["anual"]["precio"]) == 200.0


def test_solicitar_tier_solo_usa_su_propio_precio_en_cada_periodo():
    _cliente_con_gym()
    esperado = {"mensual": 20.0, "semestral": 100.0, "anual": 200.0}
    for i, (plan, precio) in enumerate(esperado.items()):
        client2 = _cliente_con_gym()  # cada uno con un gym propio: solo 1 pago pendiente a la vez
        r = client2.post(
            "/suscripciones/solicitar",
            data={"plan": plan, "referencia": f"TX-SOLO-{i}", "tier": "solo"},
            files={"comprobante": ("c.png", io.BytesIO(_PNG_1X1), "image/png")},
        )
        assert r.status_code == 201, r.text
        assert float(r.json()["monto"]) == precio, plan
        assert r.json()["tier_solicitado"] == "solo"


def test_solicitar_tier_solo_rechaza_trimestral():
    client = _cliente_con_gym()
    r = client.post(
        "/suscripciones/solicitar",
        data={"plan": "trimestral", "referencia": "TX-SOLO", "tier": "solo"},
        files={"comprobante": ("c.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 422, r.text


def test_solicitar_rechaza_tier_personalizado_por_no_ser_autoservicio():
    client = _cliente_con_gym()
    r = client.post(
        "/suscripciones/solicitar",
        data={"plan": "mensual", "referencia": "TX-PERS", "tier": "personalizado"},
        files={"comprobante": ("c.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 422, r.text


def test_confirmar_pago_con_tier_solicitado_aplica_el_tier_al_gimnasio():
    client = _cliente_con_gym()
    solicitud = client.post(
        "/suscripciones/solicitar",
        data={"plan": "mensual", "referencia": "TX-CONFIRMA", "tier": "solo"},
        files={"comprobante": ("c.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    pago_id = solicitud.json()["id"]

    pendientes = client.get("/admin/suscripciones/pagos-pendientes", headers=ADMIN_HEADERS)
    assert pendientes.status_code == 200, pendientes.text
    entrada = next(p for p in pendientes.json() if p["id"] == pago_id)
    assert entrada["tier_solicitado"] == "solo"

    r_confirmar = client.post(
        f"/admin/suscripciones/{entrada['gym_id']}/confirmar",
        json={"pago_saas_id": pago_id, "confirmado_por": "test-admin"},
        headers=ADMIN_HEADERS,
    )
    assert r_confirmar.status_code == 200, r_confirmar.text
    assert r_confirmar.json()["saas_tier"] == "solo"

    # El tier persiste — no solo en la respuesta de confirmar, sino leído de nuevo.
    estado = client.get("/suscripciones/estado")
    assert estado.json()["saas_tier"] == "solo"
    # Con el gimnasio ya en "solo", las únicas opciones son las de Solo en
    # sus 3 períodos — nada de los precios planos de SAAS_PLANES
    # ($45/$120/$220/$400), que son de estandar/clinica/personalizado.
    opciones = estado.json()["planes_disponibles"]
    assert all(o["tier"] == "solo" for o in opciones)
    assert {o["plan"] for o in opciones} == {"mensual", "semestral", "anual"}
