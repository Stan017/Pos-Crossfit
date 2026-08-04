-- ============================================================
-- Migration 001: Row Level Security (RLS) — tenant isolation
-- ============================================================
-- Protege los datos de negocio a nivel de motor PostgreSQL.
-- Si una ruta olvida filtrar por gym_id, la DB devuelve 0 filas.
--
-- Ejecutar como superuser o como el owner de las tablas.
-- Idempotente: usa IF NOT EXISTS donde aplica.
--
-- Tablas cubiertas (las 8 tablas puras de tenant):
--   miembros, planes, membresias, asistencias,
--   productos, ventas, pagos, gastos
--
-- Tablas excluidas intencionalmente:
--   gimnasios   — tabla raíz, sin gym_id
--   usuarios    — requiere acceso en login (sin JWT todavía)
--   pagos_saas  — platform admin necesita acceso cross-tenant
--   refresh_tokens, venta_items — sin gym_id
-- ============================================================

-- ── 1. Habilitar RLS ─────────────────────────────────────────

ALTER TABLE miembros    ENABLE ROW LEVEL SECURITY;
ALTER TABLE planes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE membresias  ENABLE ROW LEVEL SECURITY;
ALTER TABLE asistencias ENABLE ROW LEVEL SECURITY;
ALTER TABLE productos   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE pagos       ENABLE ROW LEVEL SECURITY;
ALTER TABLE gastos      ENABLE ROW LEVEL SECURITY;

-- FORCE RLS: también aplica al owner de las tablas.
-- Sin esto, el usuario que creó las tablas puede bypassear RLS.
ALTER TABLE miembros    FORCE ROW LEVEL SECURITY;
ALTER TABLE planes      FORCE ROW LEVEL SECURITY;
ALTER TABLE membresias  FORCE ROW LEVEL SECURITY;
ALTER TABLE asistencias FORCE ROW LEVEL SECURITY;
ALTER TABLE productos   FORCE ROW LEVEL SECURITY;
ALTER TABLE ventas      FORCE ROW LEVEL SECURITY;
ALTER TABLE pagos       FORCE ROW LEVEL SECURITY;
ALTER TABLE gastos      FORCE ROW LEVEL SECURITY;

-- ── 2. Políticas de aislamiento por tenant ────────────────────
--
-- La política compara gym_id (UUID) con la variable de sesión
-- app.current_gym_id que el backend establece por cada request.
--
-- current_setting('app.current_gym_id', true) devuelve NULL si
-- la variable no está seteada (missing_ok = true).
-- gym_id::text = NULL → NULL → false → 0 filas (correcto).
--
-- Las políticas se aplican a SELECT, INSERT, UPDATE y DELETE.
-- INSERT/UPDATE usan WITH CHECK; SELECT/DELETE usan USING. Se definen los
-- dos, idénticos, explícitamente — verificado empíricamente (ver sesión del
-- 30/07/2026) que dejar WITH CHECK implícito NO alcanza acá: un INSERT con
-- gym_id de otro tenant pasó sin bloquearse cuando la política solo tenía
-- USING. Con ambos definidos, INSERT/UPDATE con el gym_id equivocado se
-- rechazan con "new row violates row-level security policy".
--
-- IMPORTANTE — esto por sí solo NO es suficiente: el rol con el que el
-- backend se conecta hoy (el "postgres" de Supabase) tiene el atributo
-- BYPASSRLS, que ignora toda política sin importar cómo esté escrita. Ver
-- 028_rol_app_sin_bypassrls.sql — sin ese rol nuevo (y sin apuntar
-- DATABASE_URL a él), estas políticas quedan sin efecto igual.

CREATE POLICY gym_isolation ON miembros
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON planes
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON membresias
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON asistencias
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON productos
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON ventas
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON pagos
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

CREATE POLICY gym_isolation ON gastos
  USING      (gym_id::text = current_setting('app.current_gym_id', true))
  WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));

-- ── 3. Verificación ───────────────────────────────────────────
-- Ejecutar para confirmar que las políticas existen:
--
-- SELECT tablename, policyname, cmd, qual
-- FROM pg_policies
-- WHERE schemaname = 'public'
--   AND policyname = 'gym_isolation'
-- ORDER BY tablename;
--
-- Para probar el aislamiento:
-- SET app.current_gym_id = '<uuid-de-gym-A>';
-- SELECT count(*) FROM miembros;  -- debe devolver solo los de gym A
-- RESET app.current_gym_id;
-- SELECT count(*) FROM miembros;  -- debe devolver 0
