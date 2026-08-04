-- ============================================================
-- Migration 002: Audit Log
-- ============================================================
-- Registra quién hizo qué y cuándo sobre los datos de negocio.
-- Permite forensics, detección de fraude interno y resolución
-- de disputas entre staff.
--
-- Tablas auditadas: miembros, membresias, ventas, planes,
--                   productos, gastos, usuarios
-- Tablas excluidas: asistencias (solo INSERTs, sin valor forense),
--                   refresh_tokens, venta_items, pagos (hijos de ventas)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    -- gym_id y usuario_id sin REFERENCES a propósito: el log tiene que
    -- sobrevivir aunque el gimnasio o el usuario que referencia se borren
    -- después. Con FK, borrar un gimnasio fallaría por su propio audit_log
    -- (o se lo llevaría puesto en cascada) — ninguna de las dos sirve para
    -- un historial forense. Referencia "blanda" a propósito.
    gym_id      UUID        NOT NULL,
    usuario_id  UUID,                           -- NULL si fue el sistema
    accion      VARCHAR(10) NOT NULL,            -- INSERT | UPDATE | DELETE
    tabla       VARCHAR(100) NOT NULL,
    registro_id VARCHAR(100),                   -- PK del registro afectado
    payload     JSONB,                          -- campos modificados (UPDATE)
                                                -- o datos clave (INSERT/DELETE)
    ip          VARCHAR(45),
    creado_en   TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Índices para queries forenses comunes
CREATE INDEX IF NOT EXISTS ix_audit_gym_fecha
    ON audit_log (gym_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS ix_audit_tabla_registro
    ON audit_log (tabla, registro_id);

CREATE INDEX IF NOT EXISTS ix_audit_usuario
    ON audit_log (usuario_id)
    WHERE usuario_id IS NOT NULL;

-- ── Verificación ──────────────────────────────────────────────
-- SELECT * FROM audit_log ORDER BY creado_en DESC LIMIT 20;
