-- Migración 013: instructores como entidad real
--
-- Problema: clases.entrenador era texto libre, y la lista de nombres sugeridos
-- al crear una clase vivía SOLO en localStorage del navegador (no en la DB) —
-- sin lista compartida entre staff/dispositivos, y sin forma confiable de
-- contar "cuántos clientes tuvo cada instructor" (typos = instructores
-- distintos para el sistema).
--
-- clases.entrenador NO se borra ni se toca — queda como columna legado para
-- no perder el texto de clases viejas. instructor_id es la nueva fuente de
-- verdad; se backfillea creando un Instructor por cada nombre distinto ya
-- usado en clases, y enlazando esas clases al instructor recién creado.

CREATE TABLE instructores (
    id         SERIAL PRIMARY KEY,
    gym_id     UUID NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    nombre     VARCHAR(200) NOT NULL,
    telefono   VARCHAR(20),
    activo     BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_instructores_gym ON instructores(gym_id);

ALTER TABLE clases ADD COLUMN instructor_id INTEGER REFERENCES instructores(id);

-- Backfill: un instructor por cada (gym_id, nombre) distinto ya usado.
INSERT INTO instructores (gym_id, nombre, activo)
SELECT DISTINCT gym_id, entrenador, TRUE
FROM clases
WHERE entrenador IS NOT NULL AND btrim(entrenador) <> '';

-- Enlazar las clases existentes al instructor que les corresponde.
UPDATE clases c
SET instructor_id = i.id
FROM instructores i
WHERE c.gym_id = i.gym_id
  AND c.entrenador = i.nombre;
