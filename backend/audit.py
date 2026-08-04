"""
Audit log automático vía SQLAlchemy Session events.

Captura INSERT, UPDATE y DELETE sobre las tablas de negocio
y los escribe en audit_log dentro de la misma transacción.

Uso:
    import audit  # en main.py — registra los listeners al iniciar

NO usa contextvars (versión anterior lo hacía, y estaba silenciosamente roto
desde siempre — audit_log tenía 0 filas). Encontrado el 31/07/2026 mientras
se diagnosticaba un bug relacionado: FastAPI resuelve una dependencia
generadora (como get_db_tenant) y llama al endpoint en dos llamadas
SEPARADAS a run_in_threadpool — cada una copia el contextvar context de
forma independiente (contextmanager_in_threadpool en fastapi/concurrency.py
hace su propio `run_in_threadpool(cm.__enter__)`). Un ContextVar.set() hecho
dentro de la primera llamada (get_db_tenant, antes del yield) nunca es
visible en la segunda (el cuerpo real de la ruta, incluido cualquier
commit()/flush() que dispare este listener). El contextvar quedaba siempre
en su default (None) del lado del listener → `if not gym_id: return` → nunca
escribía nada.

El objeto `db` (la Session) sí viaja correctamente entre esas dos llamadas
— es un valor de retorno normal de la dependencia, no un side-effect global.
Por eso esto ahora usa `session.info`, un dict que SQLAlchemy asocia
directamente a cada instancia de Session, seteado una vez en get_db_tenant/
get_db_platform_admin y leído acá sin pasar por ningún contextvar.
"""
import json
from sqlalchemy import event, text
from sqlalchemy.orm import Session


# ── Tablas auditadas ──────────────────────────────────────────────────────────

_TABLAS = {
    "miembros", "membresias", "ventas",
    "planes", "productos", "gastos", "usuarios",
    "clases", "reservaciones", "pagos_membresia",
    "gimnasios", "pagos_saas",
}


# ── Helpers de payload ────────────────────────────────────────────────────────

def _campos_modificados(obj) -> list[str]:
    """Devuelve los atributos que cambiaron en este flush."""
    from sqlalchemy import inspect as sa_inspect
    try:
        insp = sa_inspect(obj)
        return [
            attr.key for attr in insp.attrs
            if attr.history.has_changes()
            and attr.key not in ("creado_en", "creado_por")
        ]
    except Exception:
        return []


# ── Listener principal ────────────────────────────────────────────────────────

@event.listens_for(Session, "after_flush")
def _after_flush(session: Session, flush_context) -> None:
    gym_id     = session.info.get("audit_gym_id")
    usuario_id = session.info.get("audit_usuario_id")
    ip         = session.info.get("audit_ip")

    if not gym_id:
        return  # request sin contexto de tenant (login, admin, etc.)

    entradas = []

    for obj in list(session.new):
        tabla = getattr(obj, "__tablename__", None)
        if tabla not in _TABLAS:
            continue
        entradas.append({
            "gym_id":      gym_id,
            "usuario_id":  usuario_id,
            "accion":      "INSERT",
            "tabla":       tabla,
            "registro_id": str(getattr(obj, "id", "") or ""),
            "payload":     None,
            "ip":          ip,
        })

    for obj in list(session.dirty):
        if not session.is_modified(obj):
            continue
        tabla = getattr(obj, "__tablename__", None)
        if tabla not in _TABLAS:
            continue
        campos = _campos_modificados(obj)
        entradas.append({
            "gym_id":      gym_id,
            "usuario_id":  usuario_id,
            "accion":      "UPDATE",
            "tabla":       tabla,
            "registro_id": str(getattr(obj, "id", "") or ""),
            "payload":     json.dumps({"campos": campos}) if campos else None,
            "ip":          ip,
        })

    for obj in list(session.deleted):
        tabla = getattr(obj, "__tablename__", None)
        if tabla not in _TABLAS:
            continue
        entradas.append({
            "gym_id":      gym_id,
            "usuario_id":  usuario_id,
            "accion":      "DELETE",
            "tabla":       tabla,
            "registro_id": str(getattr(obj, "id", "") or ""),
            "payload":     None,
            "ip":          ip,
        })

    if not entradas:
        return

    # Insertar vía conexión directa para evitar recursión (bypasa el ORM)
    conn = session.connection()
    conn.execute(
        text("""
            INSERT INTO audit_log
                (gym_id, usuario_id, accion, tabla, registro_id, payload, ip)
            VALUES
                (:gym_id, :usuario_id, :accion, :tabla, :registro_id,
                 CAST(:payload AS jsonb), :ip)
        """),
        entradas,
    )
