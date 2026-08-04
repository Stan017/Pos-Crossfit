-- Migración 021: pagos_saas.gym_id de ON DELETE CASCADE a RESTRICT
--
-- pagos_saas es la facturación de LA PLATAFORMA, no datos de un tenant que
-- deban desaparecer con él. Con CASCADE, borrar un gimnasio se llevaba
-- puesto su historial de ingresos sin ningún aviso. Con RESTRICT, Postgres
-- directamente rechaza el borrado de un gimnasio mientras tenga filas en
-- pagos_saas — obliga a decidir qué hacer con esos registros primero, en
-- vez de perderlos en silencio.
--
-- No existe todavía ninguna ruta que borre un gimnasio, así que este cambio
-- no afecta nada que esté corriendo hoy.

ALTER TABLE pagos_saas DROP CONSTRAINT IF EXISTS pagos_saas_gym_id_fkey;

ALTER TABLE pagos_saas
    ADD CONSTRAINT pagos_saas_gym_id_fkey
    FOREIGN KEY (gym_id) REFERENCES gimnasios(id) ON DELETE RESTRICT;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT confdeltype FROM pg_constraint WHERE conname = 'pagos_saas_gym_id_fkey';
-- confdeltype debe ser 'r' (restrict), no 'c' (cascade).
