-- Migración 016: historial médico del paciente (vertical rehab/clínica)
--
-- Tabla nueva, aditiva — no toca ninguna tabla existente. Cubre patologías
-- activas y antecedentes (lesiones/operaciones previas) del paciente, todos
-- bajo el mismo shape (descripcion/fecha/notas), distinguidos por "tipo".
-- "activa" importa sobre todo para tipo='patologia' (¿sigue en tratamiento?);
-- para lesion_previa/operacion_previa normalmente arranca en False porque ya
-- pasó, pero queda editable por si se reactiva. Restricción de quién puede
-- editar/eliminar cada registro (solo creado_por) va en la ruta, no acá.

DO $$ BEGIN
    CREATE TYPE tipohistorialmedico AS ENUM ('patologia','lesion_previa','operacion_previa');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS historial_medico (
    id          SERIAL                  PRIMARY KEY,
    gym_id      UUID                    NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    paciente_id INTEGER                 NOT NULL REFERENCES miembros(id) ON DELETE CASCADE,
    tipo        tipohistorialmedico     NOT NULL,
    descripcion TEXT                    NOT NULL,
    fecha       DATE,
    activa      BOOLEAN                 NOT NULL DEFAULT TRUE,
    notas       TEXT,
    creado_en   TIMESTAMPTZ             DEFAULT now() NOT NULL,
    creado_por  UUID                    NOT NULL REFERENCES usuarios(id)
);

CREATE INDEX IF NOT EXISTS ix_historial_medico_gym     ON historial_medico (gym_id);
CREATE INDEX IF NOT EXISTS ix_historial_medico_paciente ON historial_medico (paciente_id);

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT COUNT(*) FROM historial_medico;
