-- Migración 019: tier de plan (capacidad de staff), separado del ciclo de
-- facturación (saas_plan) y del estado de la suscripción (saas_estado).
--
-- trial=1 médico+1 asistente, estandar=3+2, clinica=6+3, personalizado=sin
-- límite (ver TIER_LIMITES en services/planes_service.py).
--
-- Backfill: los gimnasios que ya existen y NO están en trial (o sea, ya son
-- clientes reales pagando) se marcan 'estandar', no 'trial' — bajarles la
-- capacidad a alguien que ya paga sería un regresión, no una migración
-- segura. Los que sí siguen en trial se quedan en 'trial'.

DO $$ BEGIN
    CREATE TYPE saastier AS ENUM ('trial','estandar','clinica','personalizado');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE gimnasios ADD COLUMN IF NOT EXISTS saas_tier saastier;

UPDATE gimnasios SET saas_tier = 'trial'    WHERE saas_tier IS NULL AND saas_estado = 'trial';
UPDATE gimnasios SET saas_tier = 'estandar' WHERE saas_tier IS NULL;

ALTER TABLE gimnasios ALTER COLUMN saas_tier SET DEFAULT 'trial';
ALTER TABLE gimnasios ALTER COLUMN saas_tier SET NOT NULL;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT slug, saas_estado, saas_tier FROM gimnasios;
