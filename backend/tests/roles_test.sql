-- Roles para el Postgres de test — misma forma que 028/029 (mismo NOSUPERUSER/
-- NOBYPASSRLS vs BYPASSRLS), pero con contraseña de test fija, nunca la real:
-- este archivo reemplaza a 028_rol_app_sin_bypassrls.sql y
-- 029_rol_platform_bypass_rls.sql para el schema de test (ver apply_schema.py,
-- que aplica todas las migraciones EXCEPTO esas dos y corre esto en su lugar).
--
-- Sin esto, correr los tests conectados como el superusuario "postgres" del
-- container haría que las políticas de RLS quedaran inertes igual que pasó
-- en la sesión real con el rol "postgres" de Supabase — un verde falso.

CREATE ROLE app_backend WITH
    LOGIN
    PASSWORD 'test_only'
    NOSUPERUSER
    NOBYPASSRLS
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

CREATE ROLE app_platform WITH
    LOGIN
    PASSWORD 'test_only'
    NOSUPERUSER
    BYPASSRLS
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

GRANT CONNECT ON DATABASE postgres TO app_backend, app_platform;
GRANT USAGE ON SCHEMA public TO app_backend, app_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_backend, app_platform;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_backend, app_platform;
