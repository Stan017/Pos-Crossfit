-- Migración 009: dinero de Float a Numeric(10,2)
--
-- Problema: todo monto en el sistema se guardaba como Float (punto flotante
-- binario), que no puede representar exacto la mayoría de valores decimales.
-- Con suficientes sumas/restas acumuladas (abonos parciales, por ejemplo),
-- el error de redondeo se acumula y comparaciones como "saldo == 0" nunca
-- se cumplen exactas — una venta completamente pagada podía quedar atascada
-- en estado "abono" para siempre. Numeric(10,2) es aritmética decimal exacta,
-- sin ese problema.
--
-- No se tocan porcentaje_iva ni iva_default: son tasas (ej. 12.0 = 12%),
-- no montos de dinero — la imprecisión de float ahí no tiene el mismo
-- efecto acumulativo.
--
-- USING columna::numeric(10,2) hace el cast sin pérdida: el dinero ya solo
-- tenía 2 decimales de significado real.

ALTER TABLE planes
  ALTER COLUMN precio TYPE NUMERIC(10,2) USING precio::numeric(10,2);

ALTER TABLE membresias
  ALTER COLUMN precio_pagado   TYPE NUMERIC(10,2) USING precio_pagado::numeric(10,2),
  ALTER COLUMN precio_acordado TYPE NUMERIC(10,2) USING precio_acordado::numeric(10,2);

ALTER TABLE productos
  ALTER COLUMN precio_venta TYPE NUMERIC(10,2) USING precio_venta::numeric(10,2),
  ALTER COLUMN precio_costo TYPE NUMERIC(10,2) USING precio_costo::numeric(10,2);

ALTER TABLE ventas
  ALTER COLUMN subtotal  TYPE NUMERIC(10,2) USING subtotal::numeric(10,2),
  ALTER COLUMN monto_iva TYPE NUMERIC(10,2) USING monto_iva::numeric(10,2),
  ALTER COLUMN total     TYPE NUMERIC(10,2) USING total::numeric(10,2);

ALTER TABLE venta_items
  ALTER COLUMN precio_unitario TYPE NUMERIC(10,2) USING precio_unitario::numeric(10,2),
  ALTER COLUMN costo_unitario  TYPE NUMERIC(10,2) USING costo_unitario::numeric(10,2),
  ALTER COLUMN subtotal        TYPE NUMERIC(10,2) USING subtotal::numeric(10,2);

ALTER TABLE pagos
  ALTER COLUMN monto TYPE NUMERIC(10,2) USING monto::numeric(10,2);

ALTER TABLE gastos
  ALTER COLUMN monto TYPE NUMERIC(10,2) USING monto::numeric(10,2);

ALTER TABLE pagos_saas
  ALTER COLUMN monto TYPE NUMERIC(10,2) USING monto::numeric(10,2);

ALTER TABLE pagos_membresia
  ALTER COLUMN monto TYPE NUMERIC(10,2) USING monto::numeric(10,2);
