-- Migración 012: ítems de venta libres (costo extra sin producto de catálogo)
--
-- Problema: venta_items.producto_id era NOT NULL — cada ítem de una venta
-- tenía que ser un producto real del inventario. No había forma de cobrar
-- algo puntual que el cliente pidió (ej. "reposición de candado", "servicio
-- especial") sin antes dar de alta un producto falso en el catálogo, solo
-- para poder facturarlo.
--
-- producto_id pasa a nullable: NULL significa "ítem libre", y en ese caso
-- descripcion_libre trae el texto que escribió el staff en vez del nombre
-- del producto. notas es la observación puntual de ese ítem (no de la venta
-- entera, que ya tiene su propio campo notas).

ALTER TABLE venta_items
  ALTER COLUMN producto_id DROP NOT NULL,
  ADD COLUMN descripcion_libre VARCHAR(200),
  ADD COLUMN notas TEXT;
