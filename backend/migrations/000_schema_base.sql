-- Migración 000: schema base completo
--
-- Antes de esto, el schema fundacional (gimnasios, usuarios, miembros,
-- planes, membresias, asistencias, productos, ventas, venta_items, pagos,
-- gastos, refresh_tokens) más gimnasios.ruc y todo el módulo de
-- suscripciones SaaS (saas_plan/saas_estado/saas_vence_en/saas_trial_hasta,
-- tabla pagos_saas) vivían SOLO en docs/schema.sql,
-- docs/migration_add_ruc_gimnasios.sql y docs/migration_saas_suscripciones.sql
-- — nunca en esta carpeta. Corriendo solo backend/migrations/*.sql contra
-- una base vacía, 001_rls.sql fallaba: intenta proteger tablas que este
-- archivo nunca creaba.
--
-- Este archivo consolida los tres, con todo vuelto idempotente (CREATE TABLE
-- IF NOT EXISTS, CREATE TYPE envuelto en DO $$ ... EXCEPTION WHEN
-- duplicate_object) para que sea seguro correrlo también contra una base que
-- YA tiene estas tablas — no hace nada si ya existen, no falla.
--
-- Verificado antes de crear este archivo: ninguna migración 001-020 vuelve a
-- crear estas mismas tablas/columnas — son complementarias, no se pisan.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ─────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE rol_usuario AS ENUM ('admin', 'staff');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tipo_plan AS ENUM ('tiempo', 'clases');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 'pendiente_pago' NO va acá — lo agrega la migración 005
-- (ALTER TYPE ... ADD VALUE), a propósito: este archivo representa el
-- día cero real, el mismo estado que asumían las migraciones 001-004
-- antes de que existiera ese valor. docs/schema.sql (ahora movido acá)
-- lo tenía baked-in desde el principio, lo cual no reflejaba la secuencia
-- real de migraciones si se replayaban en orden.
DO $$ BEGIN
    CREATE TYPE estado_membresia AS ENUM ('activa', 'por_vencer', 'critica', 'vencida', 'cancelada');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE metodo_pago AS ENUM ('efectivo', 'transferencia', 'tarjeta');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE estado_venta AS ENUM ('pagada', 'abono', 'cancelada');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ─────────────────────────────────────────
-- GIMNASIOS (raíz del multi-tenant)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gimnasios (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre      VARCHAR(200) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    email       VARCHAR(150) NOT NULL UNIQUE,
    telefono    VARCHAR(20),
    direccion   TEXT,
    pais        VARCHAR(100) DEFAULT 'Ecuador',
    logo_url    VARCHAR(300),
    iva_default FLOAT        DEFAULT 0.0,
    activo      BOOLEAN      DEFAULT TRUE,
    creado_en   TIMESTAMPTZ  DEFAULT NOW()
);


-- ─────────────────────────────────────────
-- USUARIOS (staff / admin por gimnasio)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS usuarios (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    gym_id        UUID        NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    email         VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre        VARCHAR(200) NOT NULL,
    rol           rol_usuario  NOT NULL DEFAULT 'staff',
    activo        BOOLEAN      DEFAULT TRUE,
    creado_en     TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (gym_id, email)
);


-- ─────────────────────────────────────────
-- REFRESH TOKENS
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          SERIAL      PRIMARY KEY,
    usuario_id  UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expira_en   TIMESTAMPTZ NOT NULL,
    creado_en   TIMESTAMPTZ DEFAULT NOW()
);


-- ─────────────────────────────────────────
-- MIEMBROS (clientes del gimnasio)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS miembros (
    id                   SERIAL       PRIMARY KEY,
    gym_id               UUID         NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    nombre               VARCHAR(200) NOT NULL,
    apellido             VARCHAR(200) NOT NULL,
    email                VARCHAR(150),
    telefono             VARCHAR(20),
    cedula               VARCHAR(20),
    fecha_nacimiento     DATE,
    contacto_emergencia  VARCHAR(200),
    foto_url             VARCHAR(300),
    notas                TEXT,
    activo               BOOLEAN      DEFAULT TRUE,
    creado_en            TIMESTAMPTZ  DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_miembro_cedula
    ON miembros(gym_id, cedula)
    WHERE cedula IS NOT NULL;


-- ─────────────────────────────────────────
-- PLANES (plantillas de membresía por gimnasio)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS planes (
    id             SERIAL       PRIMARY KEY,
    gym_id         UUID         NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    nombre         VARCHAR(200) NOT NULL,
    tipo           tipo_plan    NOT NULL,
    duracion_dias  INTEGER,
    clases_total   INTEGER,
    precio         FLOAT        NOT NULL,
    activo         BOOLEAN      DEFAULT TRUE,
    creado_en      TIMESTAMPTZ  DEFAULT NOW(),
    CONSTRAINT plan_tiempo_requiere_dias
        CHECK (tipo <> 'tiempo' OR duracion_dias IS NOT NULL),
    CONSTRAINT plan_clases_requiere_clases
        CHECK (tipo <> 'clases' OR clases_total IS NOT NULL)
);


-- ─────────────────────────────────────────
-- MEMBRESÍAS (asignadas a cada miembro)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS membresias (
    id             SERIAL           PRIMARY KEY,
    gym_id         UUID             NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    miembro_id     INTEGER          NOT NULL REFERENCES miembros(id)  ON DELETE CASCADE,
    plan_id        INTEGER          NOT NULL REFERENCES planes(id),
    fecha_inicio   DATE             NOT NULL,
    fecha_fin      DATE,
    precio_pagado  FLOAT            NOT NULL,
    metodo_pago    metodo_pago      NOT NULL,
    clases_total   INTEGER,
    clases_usadas  INTEGER          DEFAULT 0,
    estado         estado_membresia NOT NULL DEFAULT 'activa',
    notas          TEXT,
    creado_en      TIMESTAMPTZ      DEFAULT NOW(),
    creado_por     UUID             REFERENCES usuarios(id)
);

-- La regla de negocio "un miembro solo puede tener una membresía activa a la
-- vez" (documentada en CLAUDE.md) — antes de este archivo, este índice
-- vivía SOLO en docs/schema.sql, sin backstop real a nivel de base de datos.
CREATE UNIQUE INDEX IF NOT EXISTS idx_membresia_activa_unica
    ON membresias(gym_id, miembro_id)
    WHERE estado = 'activa';


-- ─────────────────────────────────────────
-- ASISTENCIAS (check-in)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS asistencias (
    id            SERIAL      PRIMARY KEY,
    gym_id        UUID        NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    miembro_id    INTEGER     NOT NULL REFERENCES miembros(id),
    membresia_id  INTEGER     NOT NULL REFERENCES membresias(id),
    fecha         TIMESTAMPTZ DEFAULT NOW(),
    notas         TEXT
);


-- ─────────────────────────────────────────
-- PRODUCTOS (merch / suplementos)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS productos (
    id            SERIAL       PRIMARY KEY,
    gym_id        UUID         NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    nombre        VARCHAR(200) NOT NULL,
    categoria     VARCHAR(100),
    precio_venta  FLOAT        NOT NULL,
    precio_costo  FLOAT        NOT NULL DEFAULT 0,
    stock         INTEGER      DEFAULT 0,
    stock_minimo  INTEGER      DEFAULT 0,
    codigo_barra  VARCHAR(100),
    imagen_url    VARCHAR(300),
    activo        BOOLEAN      DEFAULT TRUE,
    creado_en     TIMESTAMPTZ  DEFAULT NOW()
);


-- ─────────────────────────────────────────
-- VENTAS (POS)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ventas (
    id             SERIAL       PRIMARY KEY,
    gym_id         UUID         NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    miembro_id     INTEGER      REFERENCES miembros(id),
    subtotal       FLOAT        NOT NULL,
    porcentaje_iva FLOAT        DEFAULT 0.0,
    monto_iva      FLOAT        DEFAULT 0.0,
    total          FLOAT        NOT NULL,
    estado         estado_venta NOT NULL DEFAULT 'pagada',
    notas          TEXT,
    creado_en      TIMESTAMPTZ  DEFAULT NOW(),
    creado_por     UUID         REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS venta_items (
    id              SERIAL  PRIMARY KEY,
    venta_id        INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        INTEGER NOT NULL,
    precio_unitario FLOAT   NOT NULL,
    subtotal        FLOAT   NOT NULL
);


-- ─────────────────────────────────────────
-- PAGOS (abonos de ventas)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pagos (
    id         SERIAL      PRIMARY KEY,
    gym_id     UUID        NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    venta_id   INTEGER     NOT NULL REFERENCES ventas(id)   ON DELETE CASCADE,
    monto      FLOAT       NOT NULL,
    metodo     metodo_pago NOT NULL DEFAULT 'efectivo',
    fecha      TIMESTAMPTZ DEFAULT NOW(),
    notas      TEXT
);


-- ─────────────────────────────────────────
-- GASTOS
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gastos (
    id          SERIAL       PRIMARY KEY,
    gym_id      UUID         NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    categoria   VARCHAR(100) NOT NULL,
    descripcion TEXT,
    monto       FLOAT        NOT NULL,
    fecha       TIMESTAMPTZ  DEFAULT NOW(),
    es_fijo     BOOLEAN      DEFAULT FALSE,
    creado_por  UUID         REFERENCES usuarios(id)
);


-- ─────────────────────────────────────────
-- ÍNDICES DE PERFORMANCE
-- ─────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_usuarios_gym          ON usuarios(gym_id);
CREATE INDEX IF NOT EXISTS idx_miembros_gym          ON miembros(gym_id);
CREATE INDEX IF NOT EXISTS idx_miembros_activo       ON miembros(gym_id, activo);
CREATE INDEX IF NOT EXISTS idx_membresias_gym        ON membresias(gym_id);
CREATE INDEX IF NOT EXISTS idx_membresias_estado     ON membresias(gym_id, estado);
CREATE INDEX IF NOT EXISTS idx_membresias_fecha_fin  ON membresias(gym_id, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_asistencias_gym_fecha ON asistencias(gym_id, fecha);
CREATE INDEX IF NOT EXISTS idx_asistencias_miembro   ON asistencias(miembro_id);
CREATE INDEX IF NOT EXISTS idx_productos_gym         ON productos(gym_id);
CREATE INDEX IF NOT EXISTS idx_ventas_gym_fecha      ON ventas(gym_id, creado_en);
CREATE INDEX IF NOT EXISTS idx_pagos_venta           ON pagos(venta_id);
CREATE INDEX IF NOT EXISTS idx_gastos_gym_fecha      ON gastos(gym_id, fecha);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash   ON refresh_tokens(token_hash);


-- ─────────────────────────────────────────
-- RUC del gimnasio (antes: docs/migration_add_ruc_gimnasios.sql)
-- ─────────────────────────────────────────

ALTER TABLE gimnasios ADD COLUMN IF NOT EXISTS ruc VARCHAR(20);


-- ─────────────────────────────────────────
-- Suscripciones SaaS (antes: docs/migration_saas_suscripciones.sql)
-- ─────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE saasplan AS ENUM ('trial', 'mensual', 'trimestral', 'anual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE saasestado AS ENUM ('trial', 'activa', 'por_vencer', 'vencida', 'suspendida');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE estadopagosaas AS ENUM ('pendiente', 'confirmado', 'rechazado');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE gimnasios
    ADD COLUMN IF NOT EXISTS saas_plan        saasplan   NOT NULL DEFAULT 'trial',
    ADD COLUMN IF NOT EXISTS saas_estado      saasestado NOT NULL DEFAULT 'trial',
    ADD COLUMN IF NOT EXISTS saas_vence_en    DATE,
    ADD COLUMN IF NOT EXISTS saas_trial_hasta DATE;

-- Gyms existentes sin trial seteado: 14 días desde hoy (mismo criterio que
-- traía el archivo original en docs/).
UPDATE gimnasios
SET saas_trial_hasta = CURRENT_DATE + INTERVAL '14 days'
WHERE saas_trial_hasta IS NULL;

CREATE TABLE IF NOT EXISTS pagos_saas (
    id              SERIAL PRIMARY KEY,
    gym_id          UUID           NOT NULL REFERENCES gimnasios(id) ON DELETE CASCADE,
    plan            saasplan       NOT NULL,
    monto           FLOAT          NOT NULL,
    metodo          VARCHAR(50)    NOT NULL DEFAULT 'transferencia',
    referencia      VARCHAR(200),
    estado          estadopagosaas NOT NULL DEFAULT 'pendiente',
    notas           TEXT,
    solicitado_en   TIMESTAMPTZ    DEFAULT NOW(),
    confirmado_en   TIMESTAMPTZ,
    confirmado_por  VARCHAR(200)
);

CREATE INDEX IF NOT EXISTS ix_pagos_saas_gym_id ON pagos_saas(gym_id);
CREATE INDEX IF NOT EXISTS ix_pagos_saas_estado ON pagos_saas(estado);

ALTER TABLE pagos_saas ADD COLUMN IF NOT EXISTS razon_rechazo TEXT;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT table_name FROM information_schema.tables WHERE table_schema='public';
