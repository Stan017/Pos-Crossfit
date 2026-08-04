-- Migración 006: vincular asistencias con reservaciones
--
-- clase_id pasa a NOT NULL: toda asistencia requiere una clase.
-- reservacion_id es nullable: walk-ins no tienen reservación previa.

ALTER TABLE asistencias
    ALTER COLUMN clase_id SET NOT NULL;

ALTER TABLE asistencias
    ADD COLUMN reservacion_id INTEGER REFERENCES reservaciones(id) ON DELETE SET NULL;
