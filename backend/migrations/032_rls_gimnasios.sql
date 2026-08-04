-- Migración 032: RLS en gimnasios
--
-- gimnasios es la tabla raíz del tenant — no tiene columna gym_id, tiene id.
-- La policy compara id (no gym_id) contra app.current_gym_id: un gym solo
-- puede ver/tocar su propia fila.
--
-- A diferencia de usuarios (031), acá hay dos consultas que por diseño
-- necesitan ver TODOS los gimnasios sin que exista todavía ningún gym_id que
-- fijar — no son un caso de "falta bootstrapear", son operaciones que
-- literalmente cruzan tenants a propósito:
--   1. login() resuelve el Gimnasio buscando por slug — es la forma en que
--      se DESCUBRE el gym_id, no se puede exigir de antemano.
--   2. register_gym() valida que el slug/email nuevo no exista en NINGÚN
--      gimnasio de la plataforma — un chequeo de unicidad global.
-- El backend resuelve esto con get_db_platform (rol app_platform,
-- BYPASSRLS a propósito — el mismo que ya usa admin_analytics.py) solo para
-- esas dos consultas puntuales; el resto del flujo de login/registro
-- (incluido el INSERT de la fila nueva de Gimnasio) sigue en la conexión
-- normal con RLS real, con set_rls_gym_id() fijando el contexto apenas se
-- conoce o se genera el id.
--
-- MISMO REQUISITO QUE 001/022/031: correr esto DESPUÉS de deployar el
-- backend que ya usa get_db_platform en esas dos consultas. Antes de eso,
-- login() no podría resolver ningún slug y register_gym() rechazaría
-- cualquier slug/email como "ya en uso" (RLS + sin contexto = 0 filas
-- visibles, no significa que estén libres).
--
-- Idempotente: usa IF NOT EXISTS donde aplica.

ALTER TABLE gimnasios ENABLE ROW LEVEL SECURITY;
ALTER TABLE gimnasios FORCE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY gym_isolation ON gimnasios
      USING      (id::text = current_setting('app.current_gym_id', true))
      WITH CHECK (id::text = current_setting('app.current_gym_id', true));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Verificación ───────────────────────────────────────────────
-- SELECT tablename, policyname, cmd
-- FROM pg_policies
-- WHERE schemaname = 'public' AND policyname = 'gym_isolation'
-- ORDER BY tablename;
-- Debe listar 16 tablas: las 15 de 001+022+031 + gimnasios.
