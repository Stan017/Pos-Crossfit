-- Migración 027: tipo de Instructor (entrenador / doctor / asistente)
--
-- Contexto: el admin de plataforma (nuevo frontend-admin/) necesita mostrar
-- cuántos entrenadores, doctores y asistentes tiene cada gym. Hasta ahora
-- Instructor es una sola tabla plana sin distinción de rol — "Terapeuta" en
-- frontend-rehab es solo texto de UI, la fila es idéntica a un coach de
-- CrossFit. Esto agrega esa distinción real a nivel de dato.
--
-- Backfill de los registros existentes por el vertical del gimnasio al que
-- pertenecen (no hay forma de adivinar "asistente" en datos viejos, así que
-- arranca en 0 para ese tipo y se corrige a mano si aplica):
--   - gimnasios.vertical = 'crossfit' → 'entrenador'
--   - gimnasios.vertical = 'medico'   → 'doctor'
--
-- Se agrega NOT NULL DEFAULT 'entrenador' en el mismo ALTER (backfill atómico
-- sin reescritura de tabla en Postgres 11+), y después se corrige a 'doctor'
-- los gimnasios médicos con el UPDATE de abajo. El DEFAULT se elimina al
-- final: InstructorCreate exige tipo explícito para altas nuevas, no hay
-- valor implícito razonable hacia adelante.

CREATE TYPE tipoinstructor AS ENUM ('entrenador', 'doctor', 'asistente');

ALTER TABLE instructores
    ADD COLUMN tipo tipoinstructor NOT NULL DEFAULT 'entrenador';

UPDATE instructores
SET tipo = 'doctor'
FROM gimnasios
WHERE instructores.gym_id = gimnasios.id
  AND gimnasios.vertical = 'medico';

ALTER TABLE instructores ALTER COLUMN tipo DROP DEFAULT;
