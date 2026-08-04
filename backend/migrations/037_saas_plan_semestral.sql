-- Migración 037: "semestral" pasa a ser un SaasPlan real.
--
-- Ya existía en la página de marketing (botón de facturación + precios
-- $220/$450 para Estándar/Clínica) pero no en el backend — SaasPlan solo
-- tenía trial/mensual/trimestral/anual. Nadie podía comprarlo de verdad:
-- Ajustes.jsx arma su selector desde SAAS_PLANES (routes/suscripciones.py),
-- que nunca tuvo esa clave. Encontrado al agregar semestral/anual al tier
-- "solo" y confirmar que el problema no era solo de Solo.

ALTER TYPE saasplan ADD VALUE IF NOT EXISTS 'semestral';

INSERT INTO schema_migrations (version) VALUES ('037_saas_plan_semestral.sql')
ON CONFLICT (version) DO NOTHING;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT unnest(enum_range(NULL::saasplan));
