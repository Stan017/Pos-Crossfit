-- Migración 029: rol de plataforma con BYPASSRLS a propósito
--
-- Contexto: 028_rol_app_sin_bypassrls.sql le sacó BYPASSRLS al rol que usa
-- el backend (app_backend), y era lo correcto — sin eso, RLS no protegía
-- nada. Pero eso dejó ciego a admin_analytics.py (y a las rutas de
-- suscripciones.py que listan/leen a través de todos los gyms): sin ningún
-- gym_id seteado en la sesión, cualquier SELECT sobre una tabla con RLS
-- (miembros, instructores, ventas, etc.) devuelve 0 filas — no es un
-- permiso denegado, es RLS haciendo exactamente lo que tiene que hacer.
--
-- El platform admin SÍ necesita ver a través de todos los tenants — es su
-- función legítima (documentada desde la migración 001: "pagos_saas —
-- platform admin necesita acceso cross-tenant"). La solución no es
-- devolverle BYPASSRLS a app_backend (eso anularía la protección para las
-- rutas de gym también) — es un rol nuevo, exclusivo para esas rutas, con
-- BYPASSRLS explícito pero sin DDL ni superuser. Mismo mínimo privilegio
-- que app_backend en todo lo demás.
--
-- Requiere agregar PLATFORM_DATABASE_URL a backend/.env después de correr
-- esto (Claude hace ese paso, igual que con app_backend en la 028).

CREATE ROLE app_platform WITH
    LOGIN
    PASSWORD 'ZQ5z_giupu-QfoyUfLJt-dwyJ3GLx6eIQIXzOL05bYw'
    NOSUPERUSER
    BYPASSRLS
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

GRANT CONNECT ON DATABASE postgres TO app_platform;
GRANT USAGE ON SCHEMA public TO app_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_platform;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_platform;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_platform;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_platform;

-- ── Verificación ──────────────────────────────────────────────
-- SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'app_platform';
-- Debe devolver rolsuper = false, rolbypassrls = true.
