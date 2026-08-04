-- Migración 020: peso y altura del miembro/paciente
--
-- Base para el nuevo perfil consolidado (identidad + biometría + membresía +
-- historial médico) en Miembros.jsx. Nullable a propósito: nadie tiene este
-- dato registrado todavía y no se le va a inventar uno — se completa de a
-- poco desde el formulario de editar/perfil.

ALTER TABLE miembros ADD COLUMN IF NOT EXISTS peso   NUMERIC(5,1);
ALTER TABLE miembros ADD COLUMN IF NOT EXISTS altura NUMERIC(5,1);

-- ── Verificación ──────────────────────────────────────────────────────────────
-- SELECT nombre, apellido, peso, altura FROM miembros LIMIT 5;
