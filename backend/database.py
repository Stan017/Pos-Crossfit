import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurado en las variables de entorno.")

# SQLite necesita check_same_thread=False, PostgreSQL no
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping: testea la conexión antes de entregarla del pool y reconecta
# transparente si Postgres ya la cerró por idle timeout (ej. Supabase) — sin
# esto, una conexión stale revienta a mitad de un request como error 500 crudo.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DEBUG habilita /docs, /redoc, /openapi.json y cookies no-secure — para
# desarrollo local con Postgres real. Nunca True en producción. Explícito vía
# .env, no derivado de nada (a diferencia de un ES_LOCAL heredado de PosRose
# que se calculaba de si DATABASE_URL era SQLite — este proyecto usa Postgres
# siempre, SQLite no soporta JSONB/UUID/RLS que el schema necesita).
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


class Base(DeclarativeBase):
    pass


# ── RLS: reafirmar el gym_id en CADA transacción de la sesión ─────────────────
#
# Historia de este bloque (31/07/2026, dos intentos):
#
# Intento 1 (roto): un listener de "checkout" a nivel de engine que leía un
# contextvar (audit._ctx_gym_id) seteado por get_db_tenant. Se rompía en dos
# niveles distintos:
#   1. El bug original que se buscaba arreglar (refresh() después de un
#      commit() en crear_clase/crear_instructor pierde el contexto porque el
#      ORM libera la conexión al pool en cada commit y el checkout previo la
#      reseteaba a blanco).
#   2. Un bug MÁS profundo, descubierto al probar el fix en vivo: FastAPI
#      resuelve una dependencia generadora (get_db_tenant) y llama al cuerpo
#      de la ruta en dos llamadas SEPARADAS a run_in_threadpool
#      (contextmanager_in_threadpool en fastapi/concurrency.py hace su propio
#      run_in_threadpool(cm.__enter__) para el "entrar" de la dependencia).
#      Cada llamada a run_in_threadpool copia el Context de contextvars de
#      forma independiente — un ContextVar.set() hecho en la primera llamada
#      (dentro de get_db_tenant) nunca es visible en la segunda (el cuerpo
#      real de la ruta). Resultado: TODAS las queries de gym veían
#      app.current_gym_id vacío, todas las tablas con RLS devolvían 0 filas.
#      (Mismo motivo por el que audit_log tenía 0 filas desde siempre — ver
#      audit.py, usaba el mismo patrón de contextvar.)
#
# Fix real: nada de contextvars. El objeto Session (`db`) sí viaja
# correctamente entre esas dos llamadas — es un valor de retorno normal de
# la dependencia, no un side-effect global — así que el gym_id se guarda en
# `session.info` (un dict que SQLAlchemy asocia a cada Session) y un
# listener de "after_begin" lo reaplica cada vez que la sesión abre una
# transacción nueva — la primera vez, y también cada vez que el ORM abre una
# implícitamente después de un commit (ej. el refresh() post-commit que
# disparó todo esto). set_config con is_local=true acá: se re-setea en cada
# transacción de todos modos, no hace falta que sobreviva más que eso.
if not DEBUG:
    @event.listens_for(SessionLocal, "after_begin")
    def _set_rls_gym_id(session, transaction, connection):
        gym_id = session.info.get("rls_gym_id", "")
        connection.execute(
            text("SELECT set_config('app.current_gym_id', :gid, true)"),
            {"gid": gym_id},
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── RLS: fijar el gym_id a mitad de una transacción ya abierta ────────────────
#
# get_db_tenant conoce el gym_id desde el JWT, antes de la primera query —
# session.info alcanza. login()/refresh()/register-gym() (routes/auth.py,
# auth.py) son distintos: usan `db: Session = Depends(get_db)` (sin gym_id
# todavía) y solo lo averiguan a MITAD de la función, después de resolver el
# Gimnasio o la fila de RefreshToken correspondiente — para ese momento la
# transacción ya está abierta (autoflush=False no importa acá, el SELECT
# anterior ya la empezó) y el listener de after_begin ya corrió con "".
#
# session.info["rls_gym_id"] = ... por sí solo NO alcanza en ese caso: el
# listener solo se re-ejecuta en la PRÓXIMA transacción de esta sesión (ej.
# el db.refresh() después de un commit), no en la que ya está en curso — la
# query que sigue en la MISMA transacción (ej. el SELECT a Usuario que viene
# justo después) seguiría viendo app.current_gym_id vacío. Por eso esto hace
# las dos cosas: reafirma set_config para la transacción actual, Y deja
# session.info seteado para que cualquier transacción nueva de esta sesión
# (post-commit) lo recoja sola vía el listener, sin tener que llamar a esto
# de nuevo después de cada commit.
def set_rls_gym_id(db, gym_id) -> None:
    db.info["rls_gym_id"] = str(gym_id)
    if not DEBUG:
        db.execute(
            text("SELECT set_config('app.current_gym_id', :gid, true)"),
            {"gid": str(gym_id)},
        )


# ── Conexión separada para platform admin (bypassea RLS a propósito) ─────────
#
# Las rutas de platform admin (admin_analytics.py, y las de suscripciones.py
# que operan sobre todos los gyms) necesitan ver a través de todos los
# tenants — es su función legítima, no un bug. No pueden usar `engine`/
# `SessionLocal` de arriba: ese rol (app_backend) tiene RLS real desde hoy,
# así que vería 0 filas en toda tabla de negocio sin un gym_id seteado.
#
# En vez de reintroducir BYPASSRLS en app_backend (lo que anularía la
# protección para las rutas de gym también), esto usa un rol nuevo,
# app_platform, con BYPASSRLS explícito PERO sin DDL ni superuser — mismo
# criterio de mínimo privilegio que app_backend, solo que este además
# bypassea RLS a propósito. Ver migración 029_rol_platform_bypass_rls.sql.
PLATFORM_DATABASE_URL = os.getenv("PLATFORM_DATABASE_URL")

if PLATFORM_DATABASE_URL:
    platform_engine = create_engine(PLATFORM_DATABASE_URL, pool_pre_ping=True)
    PlatformSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=platform_engine)
else:
    # Mientras no se corrió la 029 todavía: no hay rol de bypass separado,
    # así que las rutas de platform admin comparten la conexión normal. Si
    # PLATFORM_DATABASE_URL falta en producción, las rutas de platform admin
    # simplemente van a ver 0 filas en tablas con RLS hasta que se configure.
    PlatformSessionLocal = SessionLocal


def get_db_platform():
    db = PlatformSessionLocal()
    try:
        yield db
    finally:
        db.close()
