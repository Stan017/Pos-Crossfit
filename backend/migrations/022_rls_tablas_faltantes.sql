-- Migración 022: RLS para las tablas que quedaron afuera de la 001
--
-- 001_rls.sql cubrió las 8 tablas de tenant que existían en ese momento
-- (miembros, planes, membresias, asistencias, productos, ventas, pagos,
-- gastos). Después se agregaron instructores (013), clases/reservaciones/
-- pagos_membresia (003), e historial_medico (016) — todas con gym_id, y
-- ninguna se sumó nunca a una política RLS. Sin esto, esas 5 tablas no
-- tienen backstop de base de datos si una ruta llegara a olvidar filtrar
-- por gym_id — dependen 100% de que el código lo haga bien siempre.
--
-- MISMO REQUISITO QUE LA 001: correr esto ANTES del deploy rompe todo
-- (app.current_gym_id no está seteada todavía → toda query devuelve 0
-- filas). Se corre EN EL MISMO MOMENTO que 001_rls.sql, después de
-- deployar el backend, nunca antes.
--
-- Idempotente: usa IF NOT EXISTS donde aplica.

-- ── 1. Habilitar RLS ─────────────────────────────────────────

ALTER TABLE instructores    ENABLE ROW LEVEL SECURITY;
ALTER TABLE clases          ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservaciones   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pagos_membresia ENABLE ROW LEVEL SECURITY;
ALTER TABLE historial_medico ENABLE ROW LEVEL SECURITY;

-- FORCE RLS: también aplica al owner de las tablas (mismo criterio que 001).
ALTER TABLE instructores    FORCE ROW LEVEL SECURITY;
ALTER TABLE clases          FORCE ROW LEVEL SECURITY;
ALTER TABLE reservaciones   FORCE ROW LEVEL SECURITY;
ALTER TABLE pagos_membresia FORCE ROW LEVEL SECURITY;
ALTER TABLE historial_medico FORCE ROW LEVEL SECURITY;

-- ── 2. Políticas de aislamiento por tenant ────────────────────
-- Mismo patrón exacto que 001_rls.sql: compara gym_id contra la variable
-- de sesión app.current_gym_id que el backend setea por cada request.
-- WITH CHECK explícito además de USING — ver el comentario largo en
-- 001_rls.sql: sin WITH CHECK, un INSERT/UPDATE con el gym_id de otro
-- tenant no se bloquea. Y ninguna de las dos cosas tiene efecto real hasta
-- que el backend deje de conectarse como el rol "postgres" (BYPASSRLS) —
-- ver 028_rol_app_sin_bypassrls.sql.

DO $$ BEGIN
    CREATE POLICY gym_isolation ON instructores
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY gym_isolation ON clases
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY gym_isolation ON reservaciones
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY gym_isolation ON pagos_membresia
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY gym_isolation ON historial_medico
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── 3. Verificación ───────────────────────────────────────────
-- SELECT tablename, policyname, cmd, qual
-- FROM pg_policies
-- WHERE schemaname = 'public' AND policyname = 'gym_isolation'
-- ORDER BY tablename;
-- Debe listar las 13 tablas juntas: las 8 de la 001 + las 5 de acá.
