-- Migración 018: apellido y fecha de nacimiento del usuario
--
-- Necesarios para el formulario de registro self-service (/registro) que se
-- suma en frontend/ y frontend-rehab/. Nullable a propósito: los usuarios
-- creados antes de esto no tienen este dato y no se les va a inventar uno —
-- se exige obligatorio solo a nivel de formulario para cuentas nuevas
-- (ver RegisterGymInput en routes/auth.py), no en la base de datos.

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS apellido VARCHAR(200);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE;

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT nombre, apellido, fecha_nacimiento FROM usuarios LIMIT 5;
