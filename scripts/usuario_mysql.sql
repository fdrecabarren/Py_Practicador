-- Ejecuta este script en MySQL Workbench con tu usuario root.
-- Crea un usuario de SOLO LECTURA sobre la base olist para el practicador.
-- 1) Cambia la contrasena de la linea siguiente.
-- 2) Esa misma contrasena va en tu archivo .env (DB_PASSWORD). Nunca en el codigo.

CREATE USER IF NOT EXISTS 'practicador'@'localhost' IDENTIFIED BY 'CAMBIA_ESTA_CONTRASENA';
GRANT SELECT ON olist.* TO 'practicador'@'localhost';
FLUSH PRIVILEGES;

-- Comprobacion: debe mostrar solo "GRANT SELECT ON `olist`.* ..."
SHOW GRANTS FOR 'practicador'@'localhost';
