-- Migración 031: RLS en usuarios y audit_log
--
-- Cierra las dos tablas que 001_rls.sql había excluido a propósito:
--   usuarios    — quedaba afuera porque login/refresh corren sin JWT
--                 todavía (no hay gym_id que filtrar hasta que se resuelve
--                 quién es el usuario). Resuelto en el backend: login()
--                 y register_gym() ya conocen el gym_id de la fila de
--                 Gimnasio antes de tocar Usuario; rotar_refresh_token()
--                 ahora lo lee de refresh_tokens.gym_id (ver 030) antes de
--                 consultar Usuario. Las tres llaman a
--                 database.set_rls_gym_id() para fijar app.current_gym_id
--                 en el momento exacto en que lo aprenden.
--   audit_log   — nunca tuvo policy pese a tener gym_id. Cubre el único
--                 INSERT real (audit.py, vía conexión directa) — ese código
--                 siempre corre dentro de una transacción que ya tiene
--                 app.current_gym_id seteado al mismo gym_id que va a
--                 escribir (get_db_tenant o get_db_platform_admin), así que
--                 el WITH CHECK no le cambia nada al flujo normal.
--
-- gimnasios, pagos_saas, refresh_tokens y venta_items siguen fuera de
-- RLS por las mismas razones que documenta 001_rls.sql (tabla raíz sin
-- gym_id, acceso cross-tenant legítimo de plataforma, o sin columna
-- gym_id propia — protegidas transitivamente por la FK a una tabla que sí
-- tiene RLS). refresh_tokens en particular NO puede tener RLS aunque ya
-- tenga gym_id desde la 030: es la tabla que se consulta para AVERIGUAR
-- el tenant, exigirle gym_id de antemano para leerla rompe el login por
-- completo.
--
-- MISMO REQUISITO QUE 001/022: correr esto DESPUÉS de deployar el backend
-- que ya llama a set_rls_gym_id() en login/refresh/register-gym. Antes de
-- eso, cualquier consulta a Usuario en esos tres flujos ve 0 filas.
--
-- Idempotente: usa IF NOT EXISTS donde aplica.

-- ── 1. Habilitar RLS ─────────────────────────────────────────

ALTER TABLE usuarios   ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log  ENABLE ROW LEVEL SECURITY;

-- FORCE RLS: también aplica al owner de las tablas (mismo criterio que 001/022).
ALTER TABLE usuarios   FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log  FORCE ROW LEVEL SECURITY;

-- ── 2. Políticas de aislamiento por tenant ────────────────────
-- Mismo patrón exacto que 001/022: compara gym_id contra la variable de
-- sesión app.current_gym_id que el backend setea por cada request. WITH
-- CHECK explícito además de USING — ver el comentario largo en 001_rls.sql:
-- sin WITH CHECK, un INSERT/UPDATE con el gym_id de otro tenant no se
-- bloquea.

DO $$ BEGIN
    CREATE POLICY gym_isolation ON usuarios
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE POLICY gym_isolation ON audit_log
      USING      (gym_id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (gym_id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── 3. Verificación ───────────────────────────────────────────
-- SELECT tablename, policyname, cmd, qual
-- FROM pg_policies
-- WHERE schemaname = 'public' AND policyname = 'gym_isolation'
-- ORDER BY tablename;
-- Debe listar 15 tablas: las 13 de 001+022 + usuarios + audit_log.
