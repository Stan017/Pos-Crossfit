-- Migración 028: rol de aplicación sin BYPASSRLS/superuser
--
-- Contexto (verificado empíricamente contra la DB real, dentro de una
-- transacción con ROLLBACK, el 30/07/2026): el rol "postgres" que usa
-- DATABASE_URL hoy tiene el atributo BYPASSRLS = true (default de Supabase).
-- Row Level Security NO APLICA a ningún query hecho por un rol con ese
-- atributo — sin importar si las tablas tienen ENABLE + FORCE ROW LEVEL
-- SECURITY, ni cuántas políticas tengan. Se probó: con RLS habilitado y
-- forzado sobre "miembros" y una política gym_isolation activa, un INSERT
-- con el gym_id de OTRO tenant se permitió sin bloquearse, y un SELECT
-- devolvió filas de los dos tenants mezcladas. FORCE ROW LEVEL SECURITY
-- solo anula la excepción del DUEÑO de la tabla — no anula BYPASSRLS.
--
-- Sin este rol nuevo, correr 001_rls.sql y 022_rls_tablas_faltantes.sql no
-- cambia nada en la práctica: las políticas quedarían configuradas
-- correctamente pero inertes, mientras el backend siga conectándose como
-- "postgres".
--
-- ORDEN DE APLICACIÓN (las tres partes son independientes entre sí — se
-- puede correr esta migración antes, durante o después de 001/022, no hay
-- una dependencia real de orden en el SQL — pero el cambio SOLO tiene
-- efecto real cuando además se actualiza DATABASE_URL en backend/.env para
-- usar app_backend en vez de postgres, y se reinicia el backend):
--
--   1. Correr esta migración (028) — crea el rol, sin tocar ninguna tabla.
--   2. Correr 001 y 022 (con los WITH CHECK ya agregados) — sin efecto
--      todavía, porque el backend sigue conectado como "postgres".
--   3. Cambiar DATABASE_URL a usar app_backend (Claude hace este paso,
--      una vez confirmado que el rol existe) y reiniciar el backend.
--   4. Verificar que todo el flujo (login, POS, membresías, etc.) sigue
--      funcionando con el rol nuevo, con permisos acotados.
--
-- La contraseña de abajo es un valor generado al azar para esta migración
-- — reemplazala si preferís la tuya. Una vez corrida, guardala en un lugar
-- seguro: la vas a necesitar para actualizar backend/.env.

CREATE ROLE app_backend WITH
    LOGIN
    PASSWORD 'ZAruKkEQdha_yGvFeR0A5o2oQeCK3lT-rDEdvFt-hCE'
    NOSUPERUSER
    NOBYPASSRLS
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

GRANT CONNECT ON DATABASE postgres TO app_backend;
GRANT USAGE ON SCHEMA public TO app_backend;

-- Acceso a las tablas existentes. Un solo rol para una sola aplicación —
-- no tiene sentido enumerar tabla por tabla acá, el backend necesita
-- leer/escribir en prácticamente todo el esquema de negocio de cualquier
-- forma. Nada de DDL: sin CREATE, sin ALTER, sin DROP.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_backend;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_backend;

-- Para que las tablas/secuencias que se creen en migraciones futuras
-- también queden accesibles sin tener que acordarse de un GRANT manual
-- cada vez (mismo tipo de olvido que causó el hueco de RLS con las 5
-- tablas de la migración 022).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_backend;

-- ── Verificación ──────────────────────────────────────────────
-- SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'app_backend';
-- Debe devolver rolsuper = false, rolbypassrls = false.
