-- Migración 007: revertir asistencias.clase_id a RESTRICT + evitar check-in duplicado
--
-- Problema: la migración 004 puso clase_id en ON DELETE SET NULL para permitir
-- borrar una clase con asistencias. La migración 006 después puso clase_id
-- NOT NULL sin tocar el ondelete, dejando una combinación imposible en Postgres
-- (SET NULL no puede aplicar sobre una columna que no admite NULL).
--
-- Decisión de negocio: no se puede eliminar una clase que ya tiene asistencias
-- registradas (se rompería el historial y el conteo de clases_usadas). El
-- endpoint de borrado ahora valida esto explícitamente y devuelve 409 antes de
-- llegar a la base de datos; el FK vuelve a RESTRICT como respaldo a nivel DB.
--
-- De paso: agrega la constraint que faltaba para impedir doble check-in del
-- mismo miembro a la misma clase (bug: un retry de red podía descontar 2
-- clases por 1 visita). Antes de crearla, deduplica asistencias existentes
-- que hayan quedado duplicadas por ese bug, conservando el registro más
-- antiguo de cada (clase_id, miembro_id).

DELETE FROM asistencias a USING asistencias b
WHERE a.clase_id = b.clase_id
  AND a.miembro_id = b.miembro_id
  AND a.id > b.id;

ALTER TABLE asistencias
  DROP CONSTRAINT IF EXISTS asistencias_clase_id_fkey;

ALTER TABLE asistencias
  ADD CONSTRAINT asistencias_clase_id_fkey
    FOREIGN KEY (clase_id) REFERENCES clases(id) ON DELETE RESTRICT;

ALTER TABLE asistencias
  ADD CONSTRAINT uq_asistencia_clase_miembro UNIQUE (clase_id, miembro_id);
