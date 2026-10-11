"""Mini-Olist sintetico en SQLite, SOLO para tests y para validar el banco sin MySQL.

Tiene las mismas tablas y columnas que usa el proyecto de Olist del curso, con pocos
datos inventados (semilla fija). NO son tus datos: la app de practica usa tu MySQL.

Para que las consultas de MySQL del banco se puedan probar aqui se registran
funciones de compatibilidad (YEAR, MONTH, DAY, DATEDIFF, DATE_FORMAT basico, CONCAT).
`GROUP_CONCAT(... SEPARATOR ...)` no se puede emular: esos ejercicios llevan
`solo_mysql: true` y se saltan.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import event

from . import sql as motor_sql

DDL = """
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_unique_id TEXT, customer_zip_code_prefix INTEGER,
                        customer_city TEXT, customer_state TEXT);
CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT, order_status TEXT, order_purchase_timestamp TEXT,
                     order_approved_at TEXT, order_delivered_carrier_date TEXT, order_delivered_customer_date TEXT,
                     order_estimated_delivery_date TEXT);
CREATE TABLE order_items (order_id TEXT, order_item_id INTEGER, product_id TEXT, seller_id TEXT,
                          shipping_limit_date TEXT, price REAL, freight_value REAL,
                          PRIMARY KEY (order_id, order_item_id));
CREATE TABLE order_payments (order_id TEXT, payment_sequential INTEGER, payment_type TEXT,
                             payment_installments INTEGER, payment_value REAL);
CREATE TABLE order_reviews (review_id TEXT, order_id TEXT, review_score INTEGER, review_creation_date TEXT);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_category_name TEXT, product_name_lenght INTEGER,
                       product_description_lenght INTEGER, product_photos_qty INTEGER, product_weight_g INTEGER,
                       product_length_cm INTEGER, product_height_cm INTEGER, product_width_cm INTEGER);
CREATE TABLE sellers (seller_id TEXT PRIMARY KEY, seller_zip_code_prefix INTEGER, seller_city TEXT, seller_state TEXT);
CREATE TABLE geolocation (geolocation_zip_code_prefix INTEGER, geolocation_lat REAL, geolocation_lng REAL,
                          geolocation_city TEXT, geolocation_state TEXT);
CREATE TABLE categoria_traduccion (product_category_name TEXT, product_category_name_english TEXT);
"""

CATEGORIAS = {
    "beleza_saude": "health_beauty", "informatica_acessorios": "computers_accessories",
    "esporte_lazer": "sports_leisure", "moveis_decoracao": "furniture_decor",
    "brinquedos": "toys", "cama_mesa_banho": "bed_bath_table",
}
CIUDADES = [("sao paulo", "SP", 1000), ("rio de janeiro", "RJ", 2000), ("belo horizonte", "MG", 3000),
            ("curitiba", "PR", 4000), ("porto alegre", "RS", 5000), ("salvador", "BA", 6000)]
ESTADOS_PEDIDO = ["delivered"] * 14 + ["shipped", "canceled", "invoiced"]


def _f(d: datetime | None) -> str | None:
    return d.strftime("%Y-%m-%d %H:%M:%S") if d else None


def crear_fixture(ruta: Path | str) -> Path:
    ruta = Path(ruta)
    if ruta.exists():
        ruta.unlink()
    rnd = random.Random(7)
    con = sqlite3.connect(ruta)
    con.executescript(DDL)

    con.executemany("INSERT INTO categoria_traduccion VALUES (?,?)", list(CATEGORIAS.items()))
    for cp, (ciudad, uf, zip_) in enumerate(CIUDADES):
        for k in range(2):  # codigo postal repetido: la "trampa" de geolocation
            con.execute("INSERT INTO geolocation VALUES (?,?,?,?,?)",
                        (zip_, -23.5 + cp + k * 0.01, -46.6 + cp + k * 0.01, ciudad, uf))
    con.execute("INSERT INTO geolocation VALUES (?,?,?,?,?)", (1000, -23.5, -46.6, "sao paulo", "SP"))  # duplicado exacto

    for i in range(1, 13):
        ciudad, uf, zip_ = CIUDADES[i % len(CIUDADES)]
        con.execute("INSERT INTO sellers VALUES (?,?,?,?)", (f"s{i:02d}", zip_, ciudad.title() if i % 3 else f" {ciudad} ", uf))

    claves = list(CATEGORIAS)
    for i in range(1, 31):
        cat = None if i % 9 == 0 else claves[i % len(claves)]
        peso = None if i == 7 else rnd.choice([150, 600, 1200, 3000, 7500, 12000])
        con.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"p{i:02d}", cat, rnd.randint(20, 60), rnd.randint(100, 900), rnd.randint(1, 6), peso,
                     rnd.randint(10, 60), rnd.randint(5, 40), rnd.randint(8, 50)))

    base = datetime(2017, 1, 5)
    for i in range(1, 41):
        ciudad, uf, zip_ = CIUDADES[i % len(CIUDADES)]
        unico = f"u{(i + 1) // 2:02d}"  # 2 customer_id por cliente real en algunos casos
        con.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (f"c{i:02d}", unico, zip_, ciudad, uf))

    for i in range(1, 81):
        compra = base + timedelta(days=rnd.randint(0, 600), hours=rnd.randint(0, 23))
        estado = ESTADOS_PEDIDO[i % len(ESTADOS_PEDIDO)]
        aprob = compra + timedelta(hours=rnd.randint(1, 20))
        carrier = aprob + timedelta(days=rnd.randint(1, 4)) if estado in ("delivered", "shipped") else None
        entrega = carrier + timedelta(days=rnd.randint(3, 20)) if estado == "delivered" else None
        estimada = compra + timedelta(days=rnd.randint(10, 25))
        oid = f"o{i:03d}"
        con.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
                    (oid, f"c{rnd.randint(1, 40):02d}", estado, _f(compra), _f(aprob), _f(carrier), _f(entrega), _f(estimada)))
        for k in range(1, rnd.randint(1, 3) + 1):
            con.execute("INSERT INTO order_items VALUES (?,?,?,?,?,?,?)",
                        (oid, k, f"p{rnd.randint(1, 30):02d}", f"s{rnd.randint(1, 12):02d}", _f(aprob + timedelta(days=5)),
                         round(rnd.uniform(9, 250), 2), round(rnd.uniform(5, 40), 2)))
        for s in range(1, rnd.choice([1, 1, 1, 2, 3]) + 1):  # varias filas de pago por pedido
            tipo = rnd.choice(["credit_card", "credit_card", "boleto", "voucher", "debit_card"])
            valor = round(rnd.uniform(20, 300), 2)
            if i % 29 == 0 and s == 1:
                tipo, valor = "not_defined", 0.0
            con.execute("INSERT INTO order_payments VALUES (?,?,?,?,?)",
                        (oid, s, tipo, rnd.randint(1, 8), valor))
        if i % 10 != 0:  # algunos pedidos sin resena
            con.execute("INSERT INTO order_reviews VALUES (?,?,?,?)",
                        (f"r{i:03d}", oid, rnd.choice([1, 2, 3, 4, 4, 5, 5, 5]), _f(entrega or aprob + timedelta(days=9))))
    con.commit()
    con.close()
    return ruta


def _fecha(valor):
    if valor is None:
        return None
    return datetime.fromisoformat(str(valor)[:19].replace("T", " "))


def _registrar_compat(dbapi_con, _registro):
    dbapi_con.create_function("YEAR", 1, lambda v: _fecha(v).year if v else None)
    dbapi_con.create_function("MONTH", 1, lambda v: _fecha(v).month if v else None)
    dbapi_con.create_function("DAY", 1, lambda v: _fecha(v).day if v else None)
    dbapi_con.create_function(
        "DATEDIFF", 2, lambda a, b: (_fecha(a).date() - _fecha(b).date()).days if a and b else None)
    dbapi_con.create_function(
        "DATE_FORMAT", 2,
        lambda v, f: _fecha(v).strftime(f.replace("%i", "%M")) if v else None)


def engine_fixture(ruta: Path | str):
    """Engine SQLAlchemy de solo lectura sobre el fixture, con funciones tipo MySQL."""
    engine = motor_sql.crear_engine(f"sqlite:///{ruta}")
    event.listen(engine, "connect", _registrar_compat)
    return engine
