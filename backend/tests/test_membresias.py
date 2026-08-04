"""
Fase 1 de cobertura: membresias.py — crear/renovar, reglas de "una vigente
por miembro", pagos parciales y saldo.
"""
from datetime import date, timedelta

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_plan, crear_miembro, crear_membresia


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "memb")
    return client


def test_crear_membresia_plan_por_tiempo_calcula_fecha_fin():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)

    m = crear_membresia(client, miembro_id, plan_id)
    assert m["fecha_fin"] == str(date.today() + timedelta(days=30))
    assert m["clases_total"] is None


def test_crear_membresia_plan_por_clases_asigna_clases_total():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="clases", clases_total=12, precio=50)
    miembro_id = crear_miembro(client)

    m = crear_membresia(client, miembro_id, plan_id)
    assert m["fecha_fin"] is None
    assert m["clases_total"] == 12
    assert m["clases_usadas"] == 0


def test_crear_membresia_rechaza_miembro_con_membresia_vigente():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)

    r = client.post("/membresias/", data={
        "miembro_id":    miembro_id,
        "plan_id":       plan_id,
        "fecha_inicio":  str(date.today()),
        "precio_pagado": 50,
        "metodo_pago":   "efectivo",
    })
    assert r.status_code == 409, r.text


def test_crear_membresia_permite_agendar_despues_de_que_termine_la_vigente():
    """
    vigente.fecha_fin < datos.fecha_inicio de la nueva → la vieja se marca
    vencida sola y la nueva se crea (routes/membresias.py:238-246).
    """
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=10)
    miembro_id = crear_miembro(client)
    vieja = crear_membresia(client, miembro_id, plan_id, fecha_inicio=date.today())

    inicio_futuro = date.today() + timedelta(days=15)  # después de que la actual (10 días) termine
    r = client.post("/membresias/", data={
        "miembro_id":    miembro_id,
        "plan_id":       plan_id,
        "fecha_inicio":  str(inicio_futuro),
        "precio_pagado": 50,
        "metodo_pago":   "efectivo",
    })
    assert r.status_code == 201, r.text

    # La vieja quedó marcada vencida ANTES de su fecha_fin real (10 días,
    # todavía no pasaron) — mismo fix que en renovar_membresia.
    listado = client.get("/membresias/", params={"miembro_id": miembro_id}).json()
    estados = {m["id"]: m["estado"] for m in listado}
    assert estados[vieja["id"]] == "vencida"


def test_crear_membresia_rechaza_plan_inexistente():
    client = _cliente_con_gym()
    miembro_id = crear_miembro(client)

    r = client.post("/membresias/", data={
        "miembro_id":    miembro_id,
        "plan_id":       999999,
        "fecha_inicio":  str(date.today()),
        "precio_pagado": 50,
        "metodo_pago":   "efectivo",
    })
    assert r.status_code == 404


def test_crear_membresia_sin_pago_queda_pendiente_de_pago():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)

    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=0)
    assert m["estado"] == "pendiente_pago"
    assert float(m["saldo"]) == 50.0


def test_renovar_membresia_marca_anterior_vencida_y_crea_nueva():
    """
    renovar_membresia pone actual.estado = "vencida" en la fila vieja
    (routes/membresias.py:363) ANTES de que su fecha_fin real llegue —
    calcular_estado() ahora respeta ese "vencida" igual que "cancelada" (ver
    services/membresia_service.py), en vez de recalcularlo desde fecha_fin
    y mostrar "activa" de nuevo. Encontrado escribiendo este test: sin el
    corte, la vieja se mostraba "activa" en /membresias/ pese a estar
    reemplazada — aunque los chequeos de "una vigente por miembro" ya
    funcionaban bien porque leen la columna directo, no calcular_estado.
    """
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)
    original = crear_membresia(client, miembro_id, plan_id)

    r = client.patch(f"/membresias/{original['id']}/renovar", data={
        "plan_id":       plan_id,
        "fecha_inicio":  str(date.today()),
        "precio_pagado": 50,
        "metodo_pago":   "efectivo",
    })
    assert r.status_code == 201, r.text
    nueva = r.json()
    assert nueva["id"] != original["id"]

    listado = client.get("/membresias/", params={"miembro_id": miembro_id}).json()
    estados = {m["id"]: m["estado"] for m in listado}
    assert estados[original["id"]] == "vencida"
    assert estados[nueva["id"]] == "activa"


def test_renovar_membresia_rechaza_doble_renovacion():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)
    original = crear_membresia(client, miembro_id, plan_id)

    r1 = client.patch(f"/membresias/{original['id']}/renovar", data={
        "plan_id": plan_id, "fecha_inicio": str(date.today()),
        "precio_pagado": 50, "metodo_pago": "efectivo",
    })
    assert r1.status_code == 201

    # Reintentar renovar la MISMA (ahora vencida) membresía original —
    # ya existe una vigente distinta para el mismo miembro.
    r2 = client.patch(f"/membresias/{original['id']}/renovar", data={
        "plan_id": plan_id, "fecha_inicio": str(date.today()),
        "precio_pagado": 50, "metodo_pago": "efectivo",
    })
    assert r2.status_code == 409, r2.text


def test_renovar_membresia_inexistente_da_404():
    client = _cliente_con_gym()
    r = client.patch("/membresias/999999/renovar", data={
        "plan_id": 1, "fecha_inicio": str(date.today()),
        "precio_pagado": 50, "metodo_pago": "efectivo",
    })
    assert r.status_code == 404


def test_registrar_pago_membresia_reduce_saldo():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=100)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=0)
    assert float(m["saldo"]) == 100.0

    r = client.post(f"/membresias/{m['id']}/pagos", data={
        "monto": 40, "metodo": "efectivo",
    })
    assert r.status_code == 201, r.text
    assert float(r.json()["saldo_restante"]) == 60.0

    saldo = client.get(f"/membresias/{m['id']}/saldo").json()
    assert float(saldo["saldo"]) == 60.0
    assert float(saldo["total_pagado"]) == 40.0


def test_registrar_pago_membresia_rechaza_monto_mayor_al_saldo():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=0)

    r = client.post(f"/membresias/{m['id']}/pagos", data={
        "monto": 999, "metodo": "efectivo",
    })
    assert r.status_code == 400, r.text


def test_registrar_pago_membresia_rechaza_monto_cero():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=0)

    r = client.post(f"/membresias/{m['id']}/pagos", data={
        "monto": 0, "metodo": "efectivo",
    })
    assert r.status_code == 422, r.text


def test_alertas_incluye_membresia_pendiente_de_pago():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=50)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=0)

    alertas = client.get("/membresias/alertas").json()
    ids_pendientes = [a["membresia_id"] for a in alertas["pendientes_pago"]]
    assert m["id"] in ids_pendientes
