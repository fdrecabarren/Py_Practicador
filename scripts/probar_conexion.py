"""Comprueba la conexion a MySQL con las credenciales de .env.

Uso:  python scripts/probar_conexion.py
Muestra las tablas de la base y el numero de filas de orders. No imprime la contrasena.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor import config, sql  # noqa: E402


def main() -> int:
    if sql.url_mysql() is None:
        print("Faltan DB_USER y/o DB_PASSWORD en .env (copia .env.example como .env).")
        return 1
    print(f"Conectando a {config.DB_USER}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME} ...")
    engine = sql.crear_engine()
    ok, msg = sql.probar_conexion(engine)
    print(msg)
    if not ok:
        return 1
    esquema = sql.listar_esquema(engine)
    print(f"Tablas ({len(esquema)}): {', '.join(esquema)}")
    esperadas = {"orders", "customers", "order_items", "order_payments", "order_reviews",
                 "products", "sellers", "geolocation", "categoria_traduccion"}
    faltan = esperadas - set(esquema)
    if faltan:
        print(f"AVISO: faltan tablas que usan los ejercicios: {', '.join(sorted(faltan))}")
    else:
        r = sql.ejecutar_consulta(engine, "SELECT COUNT(*) FROM orders")
        print(f"orders tiene {r.filas[0][0]} filas. Todo listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
