"""
Aplica el schema completo (migraciones 000-032, excepto 028/029) + roles_test.sql
contra el Postgres de test. Se conecta como el superusuario "postgres" del
container — un superuser bypassea RLS igual que hacía el rol "postgres" de
Supabase, así que esto solo sirve para MONTAR el schema, nunca para correr
los tests de la app en sí (eso lo hace app_backend/app_platform, sin bypass).

028_rol_app_sin_bypassrls.sql y 029_rol_platform_bypass_rls.sql se excluyen
a propósito: tienen la contraseña REAL de producción hardcodeada. roles_test.sql
crea los mismos dos roles (mismos NOSUPERUSER/NOBYPASSRLS/BYPASSRLS), con una
contraseña de test que no es secreta.

Idempotente a nivel de "todo o nada": si `usuarios` ya existe, no hace nada
— pensado para no re-aplicar en cada corrida de pytest mientras el container
siga arriba (ver docker-compose.test.yml). Para forzar un schema limpio:
`docker compose -f backend/tests/docker-compose.test.yml down` y volver a
levantar (tmpfs, sin persistencia).
"""
import pathlib
import psycopg2

TEST_DB_URL = "postgresql://postgres:postgres@localhost:5433/postgres"

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"
_ROLES_SQL       = pathlib.Path(__file__).resolve().parent / "roles_test.sql"
_EXCLUIR = {"028_rol_app_sin_bypassrls.sql", "029_rol_platform_bypass_rls.sql"}


def _ya_aplicado(cur) -> bool:
    cur.execute("SELECT to_regclass('public.usuarios') IS NOT NULL")
    return cur.fetchone()[0]


def aplicar_schema_de_test() -> None:
    conn = psycopg2.connect(TEST_DB_URL)
    conn.autocommit = True
    cur = conn.cursor()

    if _ya_aplicado(cur):
        cur.close()
        conn.close()
        return

    archivos = sorted(
        p for p in _MIGRATIONS_DIR.glob("*.sql")
        if p.name not in _EXCLUIR
    )
    for archivo in archivos:
        cur.execute(archivo.read_text(encoding="utf-8"))

    cur.execute(_ROLES_SQL.read_text(encoding="utf-8"))

    cur.close()
    conn.close()


if __name__ == "__main__":
    aplicar_schema_de_test()
    print("Schema de test aplicado.")
