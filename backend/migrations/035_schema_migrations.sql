-- Migración 035: tabla de tracking de migraciones
--
-- Hasta hoy no había ninguna forma de saber, mirando la base real, cuáles
-- de los archivos en backend/migrations/ corrieron de verdad — esa
-- información vivía en la memoria de la conversación. Encontramos dos casos
-- reales de esto el 2026-08-01: la 025 estaba en la carpeta como si hubiera
-- corrido y nunca había tenido efecto, y miembros.fecha_ingreso se agregó a
-- mano sin ningún archivo que lo documentara.
--
-- No es Alembic ni ninguna herramienta nueva — es la tabla mínima para el
-- problema real, más una convención: de acá en adelante, cada migración
-- nueva termina con su propio INSERT a esta tabla, en el mismo archivo, así
-- que no hay paso manual extra al correrla (ver backend/check_migrations.py
-- para comparar la carpeta contra esta tabla).
--
-- El backfill de abajo asume que 000-032 y 034 ya corrieron — confirmado
-- para RLS (001/022/028-032) con verificación directa contra la base real
-- durante esta sesión, y para el resto por el historial de "ya la corrí"
-- de cada una en su momento. 033 no existe — se saltó al numerar.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    aplicada_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version) VALUES
    ('000_schema_base.sql'),
    ('001_rls.sql'),
    ('002_audit_log.sql'),
    ('003_horarios_clases.sql'),
    ('004_fix_asistencia_clase_fk.sql'),
    ('005_pendiente_pago_enum.sql'),
    ('006_asistencia_reservacion_fk.sql'),
    ('007_asistencia_restrict_delete_y_unicidad.sql'),
    ('008_venta_item_costo_historico.sql'),
    ('009_dinero_numeric.sql'),
    ('010_pago_membresia_comprobante.sql'),
    ('011_refresh_token_gracia.sql'),
    ('012_venta_item_costo_extra.sql'),
    ('013_instructores.sql'),
    ('014_instructor_ondelete_set_null.sql'),
    ('015_instructor_creado_por.sql'),
    ('016_historial_medico.sql'),
    ('017_gimnasio_vertical.sql'),
    ('018_usuario_apellido_fecha_nacimiento.sql'),
    ('019_gimnasio_saas_tier.sql'),
    ('020_miembro_peso_altura.sql'),
    ('021_pagos_saas_ondelete_restrict.sql'),
    ('022_rls_tablas_faltantes.sql'),
    ('023_unificar_metodo_pago_enum.sql'),
    ('024_indices_gym_id_pagos.sql'),
    ('025_pagos_saas_metodo_enum.sql'),
    ('026_pagos_saas_comprobante_y_gracia.sql'),
    ('027_instructor_tipo.sql'),
    ('028_rol_app_sin_bypassrls.sql'),
    ('029_rol_platform_bypass_rls.sql'),
    ('030_refresh_token_gym_id.sql'),
    ('031_rls_usuarios_audit_log.sql'),
    ('032_rls_gimnasios.sql'),
    ('034_miembro_fecha_ingreso.sql')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version) VALUES ('035_schema_migrations.sql');
