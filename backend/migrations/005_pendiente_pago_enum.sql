-- Migración 005: agregar estado 'pendiente_pago' al tipo nativo estado_membresia
--
-- La columna membresias.estado usa un enum nativo de PostgreSQL.
-- ALTER TYPE ... ADD VALUE es aditivo y no destructivo.
-- IF NOT EXISTS hace la migración idempotente.

ALTER TYPE estado_membresia ADD VALUE IF NOT EXISTS 'pendiente_pago';
