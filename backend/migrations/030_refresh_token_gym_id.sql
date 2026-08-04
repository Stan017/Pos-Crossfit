-- Migración 030: gym_id en refresh_tokens
--
-- Prerrequisito de la 031 (RLS en usuarios). rotar_refresh_token() (auth.py)
-- busca la fila de RefreshToken por token_hash SIN saber todavía a qué gym
-- pertenece — es precisamente lo que esa fila le va a decir. Para poder
-- consultar Usuario bajo RLS inmediatamente después necesita conocer el
-- gym_id ANTES de esa consulta, no después. Denormalizar gym_id acá (en vez
-- de usar un rol que bypassee RLS en ese punto) evita meter un bypass en el
-- camino de auth que corre en cada refresh de sesión (cada ~30min por cada
-- sesión abierta) — más superficie de la necesaria si mañana alguien agrega
-- otra query ahí sin notar que corre sobre una conexión sin RLS.
--
-- Es un hecho inmutable por fila: un usuario no cambia de gym sin que se le
-- cree una cuenta nueva, así que el gym_id capturado al crear el token sigue
-- siendo válido durante toda la vida del token.
--
-- Ejecutar ANTES de deployar el backend nuevo (que ya escribe gym_id en cada
-- refresh token que crea) y ANTES de la 031. Si se corre después de deployar,
-- cualquier refresh token creado en el medio queda con gym_id NULL y el
-- ALTER COLUMN ... SET NOT NULL de abajo falla.

ALTER TABLE refresh_tokens
  ADD COLUMN gym_id UUID REFERENCES gimnasios(id) ON DELETE CASCADE;

UPDATE refresh_tokens
SET gym_id = usuarios.gym_id
FROM usuarios
WHERE refresh_tokens.usuario_id = usuarios.id
  AND refresh_tokens.gym_id IS NULL;

ALTER TABLE refresh_tokens
  ALTER COLUMN gym_id SET NOT NULL;
