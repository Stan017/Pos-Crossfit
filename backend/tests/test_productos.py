"""Fase 2 de cobertura: productos.py — CRUD, soft delete, categorías."""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "prod")
    return client


def test_crear_producto_valores_por_defecto():
    client = _cliente_con_gym()
    r = client.post("/productos/", json={"nombre": "Cinta", "precio_venta": "5.00"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["stock"] == 0
    assert p["precio_costo"] == 0
    assert p["activo"] is True


def test_listar_productos_excluye_desactivados():
    client = _cliente_con_gym()
    r = client.post("/productos/", json={"nombre": "Temp", "precio_venta": "5.00"})
    producto_id = r.json()["id"]
    client.delete(f"/productos/{producto_id}")

    ids = [p["id"] for p in client.get("/productos/").json()]
    assert producto_id not in ids


def test_obtener_producto_desactivado_sigue_visible_por_id():
    """Soft delete: la fila sigue existiendo, solo se saca de los listados."""
    client = _cliente_con_gym()
    r = client.post("/productos/", json={"nombre": "Temp", "precio_venta": "5.00"})
    producto_id = r.json()["id"]
    client.delete(f"/productos/{producto_id}")

    r2 = client.get(f"/productos/{producto_id}")
    assert r2.status_code == 200
    assert r2.json()["activo"] is False


def test_actualizar_producto_parcial_no_toca_otros_campos():
    client = _cliente_con_gym()
    r = client.post("/productos/", json={
        "nombre": "Original", "precio_venta": "10.00", "stock": 5,
    })
    producto_id = r.json()["id"]

    r2 = client.patch(f"/productos/{producto_id}", json={"stock": 20})
    assert r2.status_code == 200
    actualizado = r2.json()
    assert actualizado["stock"] == 20
    assert actualizado["nombre"] == "Original"
    assert float(actualizado["precio_venta"]) == 10.0


def test_actualizar_producto_inexistente_da_404():
    client = _cliente_con_gym()
    r = client.patch("/productos/999999", json={"stock": 1})
    assert r.status_code == 404


def test_listar_categorias_deduplica_y_excluye_vacias():
    client = _cliente_con_gym()
    client.post("/productos/", json={"nombre": "A", "precio_venta": "1", "categoria": "Suplementos"})
    client.post("/productos/", json={"nombre": "B", "precio_venta": "1", "categoria": "Suplementos"})
    client.post("/productos/", json={"nombre": "C", "precio_venta": "1"})  # sin categoría

    categorias = client.get("/productos/categorias").json()
    assert categorias.count("Suplementos") == 1
    assert None not in categorias
    assert "" not in categorias
