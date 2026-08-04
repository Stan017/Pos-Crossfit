-- Migración 011: período de gracia para rotación de refresh tokens
--
-- Problema: el refresh token es de un solo uso — al rotarlo se borraba la fila
-- vieja en el momento. Dos pestañas (o un tab + un background request) que
-- refrescan casi al mismo tiempo compiten por el mismo token: la que pierde la
-- carrera presenta un token ya borrado, recibe 401 "inválido" y cierra sesión
-- aunque el usuario tenga una sesión perfectamente válida en la otra pestaña.
--
-- En vez de borrar la fila al rotar, se marca con usado_en (NULL = todavía no
-- se usó). Un token ya usado sigue aceptándose por una ventana corta de gracia
-- (10s, ver auth.py) para absorber esa carrera — cada request que entra en la
-- ventana de gracia recibe SU PROPIO refresh token nuevo, no el mismo; fuera
-- de la ventana, se rechaza como inválido igual que antes.

ALTER TABLE refresh_tokens
  ADD COLUMN usado_en TIMESTAMPTZ;
