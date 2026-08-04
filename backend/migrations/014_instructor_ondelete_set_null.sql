-- Migración 014: permitir eliminar un instructor sin clientes asignados
--
-- clases.instructor_id apuntaba a instructores con la política de borrado
-- por default de Postgres (RESTRICT): borrar un instructor con alguna clase
-- programada —aunque esa clase nunca haya tenido un solo cliente— fallaba
-- con un error crudo de FK en vez de un mensaje claro. Se cambia a
-- ON DELETE SET NULL: una clase programada sin asistencias queda "sin
-- instructor" en vez de bloquear el borrado. El bloqueo real (instructor
-- con clientes atendidos) lo hace la ruta antes de llegar a la DB
-- (routes/instructores.py, eliminar_instructor).

ALTER TABLE clases DROP CONSTRAINT clases_instructor_id_fkey;
ALTER TABLE clases ADD CONSTRAINT clases_instructor_id_fkey
    FOREIGN KEY (instructor_id) REFERENCES instructores(id) ON DELETE SET NULL;
