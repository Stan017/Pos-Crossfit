"""
Prueba el mecanismo en sí que arregla el bug de agregar_costo_extra_y_
recalcular_totales (routes/ventas.py): with_for_update() sobre la fila de
Venta tiene que bloquear a una segunda transacción concurrente hasta que la
primera haga commit.

Por qué esto no está a nivel HTTP: un test con dos threads golpeando el
endpoint (ver test_ventas_concurrencia.py) puede completar tan rápido que
las dos requests nunca lleguen a competir por la misma fila al mismo
tiempo — confirmado en esta sesión: ese test pasaba 5/5 veces incluso con
el with_for_update() sacado a propósito, no detectaba la regresión. A nivel
SQL, con las dos conexiones controladas a mano, el bloqueo es determinístico
y medible con tiempo, no depende de que el scheduler de threads interleave
en el momento justo.
"""
import threading
import time
import uuid

import psycopg2

_APP_BACKEND_URL = "postgresql://app_backend:test_only@localhost:5433/postgres"


def test_select_for_update_bloquea_segunda_transaccion_hasta_el_commit():
    gym_id = uuid.uuid4()

    # autocommit=False a propósito: set_config(..., true) es transaction-local
    # — con autocommit cada statement es su propia transacción implícita y el
    # valor se pierde antes de llegar al INSERT siguiente.
    setup = psycopg2.connect(_APP_BACKEND_URL)
    cur = setup.cursor()
    cur.execute("SELECT set_config('app.current_gym_id', %s, true)", (str(gym_id),))
    cur.execute(
        "INSERT INTO gimnasios (id, nombre, slug, email, vertical) "
        "VALUES (%s, 'X', %s, %s, 'crossfit')",
        (str(gym_id), f"slug-{gym_id.hex[:8]}", f"{gym_id.hex[:8]}@example.com"),
    )
    cur.execute(
        "INSERT INTO ventas (gym_id, subtotal, total) VALUES (%s, 100, 100) RETURNING id",
        (str(gym_id),),
    )
    venta_id = cur.fetchone()[0]
    setup.commit()
    cur.close()
    setup.close()

    eventos = {}

    def conexion_1():
        conn = psycopg2.connect(_APP_BACKEND_URL)
        cur = conn.cursor()
        cur.execute("SELECT set_config('app.current_gym_id', %s, true)", (str(gym_id),))
        cur.execute("SELECT subtotal FROM ventas WHERE id = %s FOR UPDATE", (venta_id,))
        time.sleep(0.3)  # simula el trabajo entre el SELECT y el COMMIT real de la ruta
        conn.commit()
        eventos["c1_commit"] = time.monotonic()
        cur.close()
        conn.close()

    def conexion_2():
        time.sleep(0.05)  # da tiempo a que conexion_1 tome el lock primero
        conn = psycopg2.connect(_APP_BACKEND_URL)
        cur = conn.cursor()
        cur.execute("SELECT set_config('app.current_gym_id', %s, true)", (str(gym_id),))
        inicio_espera = time.monotonic()
        cur.execute("SELECT subtotal FROM ventas WHERE id = %s FOR UPDATE", (venta_id,))
        eventos["c2_espera_seg"] = time.monotonic() - inicio_espera
        conn.commit()
        cur.close()
        conn.close()

    t1 = threading.Thread(target=conexion_1)
    t2 = threading.Thread(target=conexion_2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Cuánto esperó conexion_2 su PROPIO SELECT FOR UPDATE, medido con su
    # propio reloj — no se compara contra el timestamp de conexion_1 (eso
    # comparaba relojes de dos conexiones/threads distintos justo en el
    # instante en que Postgres libera el lock, una carrera de microsegundos
    # que nunca se cruzó en local pero sí en el runner de CI, más compartido).
    # Si FOR UPDATE no bloqueara, c2 conseguiría el lock casi al instante
    # (unos pocos ms). Bloqueando de verdad, tiene que esperar los ~0.25s que
    # le faltan a conexion_1 para terminar su sleep(0.3) + commit.
    assert eventos["c2_espera_seg"] >= 0.2
