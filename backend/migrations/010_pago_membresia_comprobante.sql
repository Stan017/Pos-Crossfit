-- Migración 010: comprobante de pago en pagos_membresia
--
-- Permite adjuntar la foto (jpg/png) del comprobante de transferencia al
-- registrar un pago de membresía (inicial, renovación o abono — los tres
-- flujos crean una fila en pagos_membresia). Nullable: la mayoría de pagos
-- en efectivo no van a tener foto, no es un dato que siempre exista.

ALTER TABLE pagos_membresia
  ADD COLUMN comprobante_url VARCHAR(300);
