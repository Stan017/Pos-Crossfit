-- ============================================================
-- Migration 003: Clases, Reservaciones, Pagos de Membresía
-- ============================================================
-- Nuevos módulos: Horarios (clases + reservaciones) y
--                 Abonos vinculados a membresías.
-- Modifica:       asistencias (+ clase_id)
--                 membresias  (+ precio_acordado)
-- ============================================================

-- ── Tipos ENUM ───────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE metodopago AS ENUM ('efectivo','transferencia','tarjeta');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE estadoclase AS ENUM ('programada','en_curso','completada','cancelada');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE estadoreservacion AS ENUM ('confirmada','cancelada','no_show');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Tabla: clases ─────────────────────────────────────────────────────────────
-- Instancias de clases programadas. No hay plantilla — staff crea cada clase
-- directamente con su fecha, horario y coach.

CREATE TABLE IF NOT EXISTS clases (
    id          SERIAL          PRIMARY KEY,
    gym_id      UUID            NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    fecha       DATE            NOT NULL,
    hora_inicio TIME            NOT NULL,
    hora_fin    TIME            NOT NULL,
    nombre      VARCHAR(200)    NOT NULL,
    entrenador  VARCHAR(200),
    capacidad   INTEGER         NOT NULL DEFAULT 20,
    estado      estadoclase     NOT NULL DEFAULT 'programada',
    notas       TEXT,
    creado_en   TIMESTAMPTZ     DEFAULT now() NOT NULL,
    creado_por  UUID            REFERENCES usuarios(id)
);

CREATE INDEX IF NOT EXISTS ix_clases_gym_fecha ON clases (gym_id, fecha);

-- ── Tabla: reservaciones ──────────────────────────────────────────────────────
-- Reserva de un miembro a una clase concreta.
-- canal: 'staff' (panel web) | 'whatsapp' (bot futuro) | 'web' (auto-servicio futuro)

CREATE TABLE IF NOT EXISTS reservaciones (
    id            SERIAL              PRIMARY KEY,
    gym_id        UUID                NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    clase_id      INTEGER             NOT NULL REFERENCES clases(id) ON DELETE CASCADE,
    miembro_id    INTEGER             NOT NULL REFERENCES miembros(id),
    estado        estadoreservacion   NOT NULL DEFAULT 'confirmada',
    canal         VARCHAR(50)         NOT NULL DEFAULT 'staff',
    reservado_en  TIMESTAMPTZ         DEFAULT now() NOT NULL,
    reservado_por UUID                REFERENCES usuarios(id),
    UNIQUE (clase_id, miembro_id)
);

CREATE INDEX IF NOT EXISTS ix_reservaciones_gym_clase ON reservaciones (gym_id, clase_id);
CREATE INDEX IF NOT EXISTS ix_reservaciones_miembro   ON reservaciones (miembro_id);

-- ── Tabla: pagos_membresia ────────────────────────────────────────────────────
-- Pagos individuales (abonos) contra una membresía.
-- Permite membresías pagadas en cuotas.

CREATE TABLE IF NOT EXISTS pagos_membresia (
    id             SERIAL      PRIMARY KEY,
    gym_id         UUID        NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    membresia_id   INTEGER     NOT NULL REFERENCES membresias(id) ON DELETE CASCADE,
    monto          FLOAT       NOT NULL,
    metodo         metodopago  NOT NULL,
    fecha          TIMESTAMPTZ DEFAULT now() NOT NULL,
    notas          TEXT,
    registrado_por UUID        REFERENCES usuarios(id)
);

CREATE INDEX IF NOT EXISTS ix_pagos_mem_membresia ON pagos_membresia (membresia_id);

-- ── ALTER: asistencias — agregar clase_id ─────────────────────────────────────
-- NULL = open gym walk-in (sin clase específica)
-- NOT NULL = asistió a una clase concreta

ALTER TABLE asistencias ADD COLUMN IF NOT EXISTS clase_id INTEGER REFERENCES clases(id);

-- ── ALTER: membresias — agregar precio_acordado ───────────────────────────────
-- precio_acordado: precio total pactado para la membresía
-- saldo = precio_acordado - SUM(pagos_membresia.monto)

ALTER TABLE membresias ADD COLUMN IF NOT EXISTS precio_acordado FLOAT;

-- ── Migración de datos ────────────────────────────────────────────────────────
-- Backfill precio_acordado para registros existentes

UPDATE membresias
SET precio_acordado = precio_pagado
WHERE precio_acordado IS NULL;

-- Crear registro inicial en pagos_membresia por cada membresía existente
-- que tenga un precio_pagado real (evita duplicados con el NOT EXISTS)

INSERT INTO pagos_membresia (gym_id, membresia_id, monto, metodo, fecha, notas)
SELECT
    m.gym_id,
    m.id,
    m.precio_pagado,
    m.metodo_pago::text::metodopago,
    m.creado_en,
    'Migración inicial'
FROM membresias m
WHERE m.precio_pagado IS NOT NULL
  AND m.precio_pagado > 0
  AND NOT EXISTS (
      SELECT 1 FROM pagos_membresia pm WHERE pm.membresia_id = m.id
  );

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT COUNT(*) FROM clases;
-- SELECT COUNT(*) FROM reservaciones;
-- SELECT COUNT(*) FROM pagos_membresia;
-- SELECT id, precio_pagado, precio_acordado FROM membresias LIMIT 5;
