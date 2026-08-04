-- Migración 015: rastrear quién creó cada instructor
--
-- Para que "Eliminar" en Instructores.jsx solo lo pueda hacer el admin que
-- dio de alta al instructor (evita que un admin borre algo que dio de alta
-- otro, sin que medie acuerdo entre ambos). Nullable e intencional: los
-- instructores creados por el backfill de la migración 013 no tienen un
-- admin real detrás — para esos, cualquier admin puede borrar (ver
-- eliminar_instructor en routes/instructores.py).

ALTER TABLE instructores ADD COLUMN creado_por UUID REFERENCES usuarios(id);
