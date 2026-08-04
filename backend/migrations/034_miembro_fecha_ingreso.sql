-- Migración 034: documenta miembros.fecha_ingreso
--
-- Encontrado el 01/08/2026 armando el test suite: models.py y el schema
-- Pydantic (MiembroInput) exigen fecha_ingreso como campo obligatorio desde
-- siempre, y la columna existe y funciona en la base real (date, NOT NULL,
-- sin default, cero filas nulas) — pero no aparece en NINGÚN archivo de
-- migración. Se agregó a mano contra la base en algún momento, sin dejar
-- rastro. Comparé cada columna de cada modelo contra la base real
-- (los 19 modelos, en las dos direcciones) — es el único caso de este tipo
-- en todo el schema.
--
-- IF NOT EXISTS: no-op en la base real (la columna ya existe ahí);
-- construye la columna en cualquier entorno levantado desde cero a partir
-- de las migraciones (este test suite, o el día que haga falta un
-- staging/disaster recovery). Sin default a propósito — igual que en la
-- base real, y el schema Pydantic ya lo exige obligatorio en el request.

ALTER TABLE miembros
    ADD COLUMN IF NOT EXISTS fecha_ingreso DATE NOT NULL;
