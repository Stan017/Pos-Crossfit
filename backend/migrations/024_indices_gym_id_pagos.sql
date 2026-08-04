-- Migración 024: índices de gym_id faltantes en pagos y pagos_membresia
--
-- Toda otra tabla de tenant tiene al menos un índice que cubre gym_id.
-- Estas dos quedaron afuera desde que se crearon — pagos.gym_id se filtra
-- directo en routes/pagos.py, y las dos escalan con full scan a medida que
-- crecen los datos.

CREATE INDEX IF NOT EXISTS idx_pagos_gym           ON pagos(gym_id);
CREATE INDEX IF NOT EXISTS idx_pagos_membresia_gym ON pagos_membresia(gym_id);

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT indexname FROM pg_indexes WHERE tablename IN ('pagos','pagos_membresia');
