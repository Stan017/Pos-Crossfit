-- Migración 017: a qué vertical/frontend pertenece cada gimnasio
--
-- Antes de esto, cualquier gym_slug + password correctos entraban a
-- cualquiera de los dos frontends (CrossFit o médico/rehab) sin que el
-- backend supiera ni le importara cuál lo llamaba — solo mostraba las
-- etiquetas equivocadas, sin fuga de datos real (gym_id sigue aislando todo),
-- pero confuso. /auth/login ahora exige que el "vertical" que manda el
-- frontend (una constante fija por build, no algo que el usuario elige)
-- coincida con el de la fila real, cayendo en el mismo 401 genérico si no.
--
-- NOT NULL desde el día uno: no hay estado "todavía sin vertical" válido.
-- Backfill a 'crossfit' porque hoy el 100% de los gimnasios existentes son
-- del vertical original — el médico/rehab es el primero del otro tipo y se
-- crea después de esta migración.

DO $$ BEGIN
    CREATE TYPE verticalnegocio AS ENUM ('crossfit','medico');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE gimnasios ADD COLUMN IF NOT EXISTS vertical verticalnegocio;

UPDATE gimnasios SET vertical = 'crossfit' WHERE vertical IS NULL;

ALTER TABLE gimnasios ALTER COLUMN vertical SET NOT NULL;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT slug, vertical FROM gimnasios;
