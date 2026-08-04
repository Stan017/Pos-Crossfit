-- Migración 004: Fix FK asistencias.clase_id → clases.id
--
-- Problema: la FK no tenía ON DELETE definido (default RESTRICT).
-- Al eliminar una clase con asistencias asociadas, PostgreSQL lanzaba
-- ForeignKeyViolation. El campo ya es nullable (walk-in sin clase),
-- así que SET NULL preserva el registro histórico y permite el delete.

ALTER TABLE asistencias
  DROP CONSTRAINT IF EXISTS asistencias_clase_id_fkey;

ALTER TABLE asistencias
  ADD CONSTRAINT asistencias_clase_id_fkey
    FOREIGN KEY (clase_id) REFERENCES clases(id) ON DELETE SET NULL;
