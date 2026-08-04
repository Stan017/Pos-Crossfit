-- Migración 025: pagos_saas.metodo de texto libre a enum real
--
-- Era String(50) libre con default "transferencia", sin ninguna validación
-- — a diferencia de pagos.metodo y pagos_membresia.metodo, que ya usan el
-- enum metodo_pago. Un typo como "trasnferencia" se guardaba sin quejarse
-- en un dato de facturación de la plataforma. Verificado antes de este
-- cambio: el único lugar del código que escribe este campo
-- (routes/suscripciones.py, solicitar_suscripcion) siempre pone
-- literalmente 'transferencia', así que el cast de los datos existentes es
-- seguro — no hay ningún valor guardado que no encaje en el enum.

-- Postgres necesita el DROP DEFAULT en un paso separado ANTES del cambio de
-- tipo: con TYPE y SET DEFAULT en el mismo ALTER TABLE (como estaba antes),
-- intenta recastear el default VIEJO ('transferencia'::character varying)
-- al tipo nuevo como parte de aplicar el TYPE, y ese recast automático
-- falla — el SET DEFAULT nuevo nunca llega a tener efecto porque el error
-- pasa antes. Encontrado el 01/08/2026 armando el test suite: esta
-- migración estaba en la carpeta como si ya hubiera corrido, pero
-- pagos_saas.metodo en la base real seguía siendo varchar — nunca se había
-- aplicado de verdad. Falta correrla de nuevo, ahora sí con esta versión.
ALTER TABLE pagos_saas
    ALTER COLUMN metodo DROP DEFAULT;

ALTER TABLE pagos_saas
    ALTER COLUMN metodo TYPE metodo_pago USING metodo::metodo_pago;

ALTER TABLE pagos_saas
    ALTER COLUMN metodo SET DEFAULT 'transferencia'::metodo_pago;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT udt_name FROM information_schema.columns
-- WHERE table_name = 'pagos_saas' AND column_name = 'metodo';
-- Debe decir 'metodo_pago'.
