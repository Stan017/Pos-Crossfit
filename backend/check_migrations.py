"""
Compara backend/migrations/*.sql contra la tabla schema_migrations (migración
035) en la base real. Solo lectura — usa las credenciales normales de la app
(DATABASE_URL), no necesita nada nuevo ni privilegios de DDL.

Uso:
    cd backend && python check_migrations.py
"""
import os
import pathlib

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent / "migrations"


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está configurado en backend/.env")

    archivos_locales = {p.name for p in _MIGRATIONS_DIR.glob("*.sql")}

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    try:
        cur.execute("SELECT version FROM schema_migrations")
    except psycopg2.errors.UndefinedTable:
        print(
            "La tabla schema_migrations no existe todavía — correr "
            "035_schema_migrations.sql contra la base real primero."
        )
        return
    aplicadas = {r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()

    sin_aplicar = sorted(archivos_locales - aplicadas)
    sin_archivo = sorted(aplicadas - archivos_locales)

    if not sin_aplicar and not sin_archivo:
        print(f"OK — {len(aplicadas)} migraciones, carpeta y base coinciden.")
        return

    if sin_aplicar:
        print(f"Archivos en backend/migrations/ que la base dice que NO corrieron ({len(sin_aplicar)}):")
        for nombre in sin_aplicar:
            print(f"  - {nombre}")

    if sin_archivo:
        print(f"Registradas como aplicadas pero sin archivo local ({len(sin_archivo)}):")
        for nombre in sin_archivo:
            print(f"  - {nombre}")


if __name__ == "__main__":
    main()
