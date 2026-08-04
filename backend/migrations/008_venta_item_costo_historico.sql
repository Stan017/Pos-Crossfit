-- Migración 008: costo histórico en venta_items
--
-- Problema: finanzas.py calculaba el costo de ventas haciendo JOIN contra
-- Producto.precio_costo (el costo ACTUAL del producto), no el costo vigente
-- al momento de la venta. Cambiar el costo de un producto hoy reescribía
-- retroactivamente la ganancia bruta/neta de meses ya cerrados.
--
-- Se agrega costo_unitario a venta_items, capturado en el momento de la
-- venta desde ahora en adelante. Para ítems ya existentes no hay forma de
-- recuperar el costo histórico real; se usa el precio_costo actual del
-- producto como mejor aproximación disponible (es el mismo valor que la
-- query rota ya estaba usando para esos períodos).

ALTER TABLE venta_items
  ADD COLUMN costo_unitario DOUBLE PRECISION;

UPDATE venta_items vi
SET costo_unitario = p.precio_costo
FROM productos p
WHERE vi.producto_id = p.id;

UPDATE venta_items
SET costo_unitario = 0
WHERE costo_unitario IS NULL;

ALTER TABLE venta_items
  ALTER COLUMN costo_unitario SET NOT NULL,
  ALTER COLUMN costo_unitario SET DEFAULT 0;
