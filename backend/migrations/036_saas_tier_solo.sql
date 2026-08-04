-- Migración 036: tier "solo" ($20/mes, mismos límites que trial pero pago) +
-- tier_solicitado en pagos_saas para que el gym pueda pedir un cambio de
-- tier junto con su solicitud de pago (ver services/planes_service.py y
-- routes/suscripciones.py). El cambio de tier solo se aplica cuando el
-- platform admin confirma el pago (confirmar_pago) — nunca al solicitar,
-- mismo criterio que ya existe para saas_plan/saas_vence_en.

ALTER TYPE saastier ADD VALUE IF NOT EXISTS 'solo';

ALTER TABLE pagos_saas ADD COLUMN IF NOT EXISTS tier_solicitado saastier;

INSERT INTO schema_migrations (version) VALUES ('036_saas_tier_solo.sql')
ON CONFLICT (version) DO NOTHING;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT unnest(enum_range(NULL::saastier));
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'pagos_saas' AND column_name = 'tier_solicitado';
