"""
Prueba las políticas gym_isolation en sí (001/022/031/032), con SQL crudo,
sin pasar por ninguna ruta HTTP ni por el filtro .filter(gym_id == ...) que
ya tiene cada ruta.

Por qué esto no está en test_auth_rls.py: ahí se prueba que la APP filtra
bien end-to-end — y sigue filtrando bien con RLS activo — pero ninguna ruta
real puede probar el backstop en sí, porque ninguna ruta real debería (ni
debe) dejar de filtrar por gym_id. El valor de RLS es específicamente para
el día que una ruta se olvide — y ese escenario solo se puede reproducir
saltándose la app y mandando la query sin filtro directo a Postgres, como
acá. Confirmado con un experimento real durante esta sesión: apuntar
DATABASE_URL al rol app_platform (bypass) NO hizo fallar
test_usuarios_no_ve_datos_de_otro_gym, porque routes/usuarios.py ya filtra
por Usuario.gym_id explícito — ese test prueba la ruta, no el backstop.

Conectado como app_backend (NOBYPASSRLS) — el mismo rol que usa el backend
real. Un superusuario bypassea RLS sin importar las políticas.
"""
import uuid

import psycopg2
import pytest

_APP_BACKEND_URL = "postgresql://app_backend:test_only@localhost:5433/postgres"


def _conectar():
    conn = psycopg2.connect(_APP_BACKEND_URL)
    conn.autocommit = False
    return conn


def _set_gym(cur, gym_id) -> None:
    cur.execute(
        "SELECT set_config('app.current_gym_id', %s, true)",
        (str(gym_id) if gym_id else "",),
    )


def _crear_gimnasio(cur, gym_id) -> None:
    # gimnasios filtra por id (no tiene columna gym_id) — el contexto tiene
    # que ser el id de la fila que se está por insertar.
    _set_gym(cur, gym_id)
    cur.execute(
        "INSERT INTO gimnasios (id, nombre, slug, email, vertical) "
        "VALUES (%s, %s, %s, %s, 'crossfit')",
        (gym_id, f"Gym {gym_id}", f"slug-{gym_id.hex[:8]}", f"{gym_id.hex[:8]}@example.com"),
    )


def _crear_miembro(cur, gym_id, nombre) -> None:
    _set_gym(cur, gym_id)
    cur.execute(
        "INSERT INTO miembros (gym_id, nombre, apellido, fecha_ingreso) "
        "VALUES (%s, %s, %s, CURRENT_DATE)",
        (gym_id, nombre, nombre),
    )


def _crear_usuario(cur, gym_id, email) -> None:
    _set_gym(cur, gym_id)
    cur.execute(
        "INSERT INTO usuarios (id, gym_id, email, password_hash, nombre, rol) "
        "VALUES (%s, %s, %s, 'x', 'X', 'admin')",
        (uuid.uuid4(), gym_id, email),
    )


# ── El backstop en sí: SELECT sin WHERE ─────────────────────────────────────

def test_miembros_select_sin_filtro_no_ve_otro_tenant():
    """Tabla cubierta desde la 001, de antes de esta sesión — smoke test de base."""
    gym_a, gym_b = uuid.uuid4(), uuid.uuid4()
    conn = _conectar()
    cur = conn.cursor()
    _crear_gimnasio(cur, gym_a)
    _crear_gimnasio(cur, gym_b)
    _crear_miembro(cur, gym_a, "A")
    _crear_miembro(cur, gym_b, "B")
    conn.commit()

    _set_gym(cur, gym_a)
    cur.execute("SELECT nombre FROM miembros")  # sin WHERE, a propósito
    filas = [r[0] for r in cur.fetchall()]
    conn.rollback()
    cur.close()
    conn.close()

    assert filas == ["A"]


def test_usuarios_select_sin_filtro_no_ve_otro_tenant():
    """El gap que cerramos hoy (migración 031) — mismo experimento que arriba."""
    gym_a, gym_b = uuid.uuid4(), uuid.uuid4()
    conn = _conectar()
    cur = conn.cursor()
    _crear_gimnasio(cur, gym_a)
    _crear_gimnasio(cur, gym_b)
    _crear_usuario(cur, gym_a, "a@example.com")
    _crear_usuario(cur, gym_b, "b@example.com")
    conn.commit()

    _set_gym(cur, gym_a)
    cur.execute("SELECT email FROM usuarios")  # sin WHERE
    filas = [r[0] for r in cur.fetchall()]
    conn.rollback()
    cur.close()
    conn.close()

    assert filas == ["a@example.com"]


def test_gimnasios_select_sin_filtro_no_ve_otro_tenant():
    """gimnasios (migración 032) — la policy compara id, no gym_id."""
    gym_a, gym_b = uuid.uuid4(), uuid.uuid4()
    conn = _conectar()
    cur = conn.cursor()
    _crear_gimnasio(cur, gym_a)
    _crear_gimnasio(cur, gym_b)
    conn.commit()

    _set_gym(cur, gym_a)
    cur.execute("SELECT id FROM gimnasios")  # sin WHERE
    filas = [r[0] for r in cur.fetchall()]
    conn.rollback()
    cur.close()
    conn.close()

    assert filas == [str(gym_a)]  # psycopg2 devuelve UUID como str por default


def test_audit_log_select_sin_filtro_no_ve_otro_tenant():
    """audit_log (migración 031) — sin FK a propósito, igual respeta la policy."""
    gym_a, gym_b = uuid.uuid4(), uuid.uuid4()
    conn = _conectar()
    cur = conn.cursor()
    _crear_gimnasio(cur, gym_a)
    _crear_gimnasio(cur, gym_b)

    _set_gym(cur, gym_a)
    cur.execute(
        "INSERT INTO audit_log (gym_id, accion, tabla) VALUES (%s, 'INSERT', 'miembros')",
        (gym_a,),
    )
    _set_gym(cur, gym_b)
    cur.execute(
        "INSERT INTO audit_log (gym_id, accion, tabla) VALUES (%s, 'INSERT', 'miembros')",
        (gym_b,),
    )
    conn.commit()

    _set_gym(cur, gym_a)
    cur.execute("SELECT gym_id FROM audit_log")  # sin WHERE
    filas = cur.fetchall()
    conn.rollback()
    cur.close()
    conn.close()

    assert filas == [(str(gym_a),)]  # psycopg2 devuelve UUID como str por default


# ── Sin contexto: 0 filas, nunca todas ───────────────────────────────────────

def test_sin_contexto_no_ve_nada():
    """
    Una conexión que nunca llamó set_rls_gym_id (app.current_gym_id vacío)
    tiene que ver CERO filas, no todas — es la falla segura: current_setting
    devuelve NULL, gym_id::text = NULL es NULL (nunca true), no un comodín.
    """
    gym_a = uuid.uuid4()
    conn = _conectar()
    cur = conn.cursor()
    _crear_gimnasio(cur, gym_a)
    _crear_miembro(cur, gym_a, "X")
    conn.commit()

    _set_gym(cur, None)
    cur.execute("SELECT count(*) FROM miembros")
    total = cur.fetchone()[0]
    conn.rollback()
    cur.close()
    conn.close()

    assert total == 0


# ── WITH CHECK: no solo lectura, también escritura ──────────────────────────

def test_insert_con_gym_id_de_otro_tenant_se_rechaza():
    """
    El bug real que encontramos y arreglamos en la 001/022 (USING solo no
    alcanza): un INSERT con el gym_id de OTRO tenant, mientras el contexto
    de la sesión es gym_a, tiene que rechazarse duro — no silenciarse.
    """
    gym_a, gym_b = uuid.uuid4(), uuid.uuid4()
    conn = _conectar()
    cur = conn.cursor()
    _crear_gimnasio(cur, gym_a)
    _crear_gimnasio(cur, gym_b)
    conn.commit()

    _set_gym(cur, gym_a)
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        cur.execute(
            "INSERT INTO miembros (gym_id, nombre, apellido, fecha_ingreso) "
            "VALUES (%s, 'X', 'X', CURRENT_DATE)",
            (gym_b,),
        )
    conn.rollback()
    cur.close()
    conn.close()
