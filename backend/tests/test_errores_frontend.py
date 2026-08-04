"""
Cobertura de errores_frontend.py: endpoint público (sin auth a propósito —
un crash puede pasar en la pantalla de Login), devuelve 204 sin cuerpo,
valida límites de tamaño, y loguea con logger "crossfit_saas".
"""
import logging

from conftest import nuevo_client


def _payload(**extra):
    return {
        "mensaje": "TypeError: x is undefined",
        "url":     "https://app.example.com/miembros",
        **extra,
    }


def test_reportar_error_devuelve_204_sin_auth():
    client = nuevo_client()  # nunca logueado
    r = client.post("/errores-frontend", json=_payload(
        stack="at App.jsx:10", contexto="react-error-boundary",
    ))
    assert r.status_code == 204, r.text
    assert r.content == b""


def test_reportar_error_sin_mensaje_da_422():
    client = nuevo_client()
    r = client.post("/errores-frontend", json={"url": "https://app.example.com/"})
    assert r.status_code == 422


def test_reportar_error_rechaza_mensaje_demasiado_largo():
    client = nuevo_client()
    r = client.post("/errores-frontend", json=_payload(mensaje="x" * 2001))
    assert r.status_code == 422


def test_reportar_error_queda_en_el_log_del_backend(caplog):
    client = nuevo_client()
    with caplog.at_level(logging.ERROR, logger="crossfit_saas"):
        client.post("/errores-frontend", json=_payload(
            mensaje="Error unico de test 12345", contexto="window-error",
        ))
    assert "Error unico de test 12345" in caplog.text
    assert "window-error" in caplog.text
