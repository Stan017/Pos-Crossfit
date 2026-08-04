-- Migración 023: unificar el tipo "método de pago" — quedan dos por error
--
-- migración 003 creó un tipo `metodopago` (sin guion bajo) propio para
-- pagos_membresia.metodo, en vez de reusar `metodo_pago` (con guion bajo)
-- que ya existía desde el schema base (ver 000_schema_base.sql) para
-- pagos.metodo y membresias.metodo_pago. Mismos 3 valores exactos, dos
-- tipos Postgres distintos para el mismo concepto — agregar un método de
-- pago nuevo en el futuro requeriría acordarse de alterar los dos, o
-- quedan desincronizados sin ningún aviso.
--
-- No hace falta tocar models.py ni ninguna ruta: SQLAlchemy no ata la
-- columna a un nombre de tipo Postgres específico, solo a los valores —
-- el cambio es enteramente de base de datos.

ALTER TABLE pagos_membresia
    ALTER COLUMN metodo TYPE metodo_pago USING metodo::text::metodo_pago;

DROP TYPE IF EXISTS metodopago;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT udt_name FROM information_schema.columns
-- WHERE table_name = 'pagos_membresia' AND column_name = 'metodo';
-- Debe decir 'metodo_pago', no 'metodopago'.
