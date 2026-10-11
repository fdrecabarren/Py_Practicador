import pytest

from motor import sql
from motor.fixture_olist import crear_fixture, engine_fixture


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    ruta = crear_fixture(tmp_path_factory.mktemp("fx") / "olist.db")
    return engine_fixture(ruta)


# ------------------------------------------------------------ validacion
@pytest.mark.parametrize("consulta", [
    "SELECT * FROM orders",
    "select 1;",
    "WITH a AS (SELECT 1 AS x) SELECT x FROM a",
    "  -- comentario\n SELECT 'a;b' AS t",
    "SELECT review_creation_date FROM order_reviews",          # create dentro de un nombre: permitido
    "SELECT 'delete me' AS t",                                  # palabra prohibida dentro de un texto: permitido
    "SELECT /* update */ 1",
])
def test_consultas_permitidas(consulta):
    assert sql.validar_consulta(consulta)[0] is None


@pytest.mark.parametrize("consulta", [
    "", "   ", "DELETE FROM orders", "UPDATE orders SET order_status='x'", "DROP TABLE orders",
    "INSERT INTO orders VALUES (1)", "SELECT 1; SELECT 2", "SELECT 1; DROP TABLE orders",
    "WITH x AS (SELECT 1) DELETE FROM orders", "SELECT * FROM orders INTO OUTFILE 'x'",
    "SELECT SLEEP(100)", "CREATE TABLE t (a int)", "SHOW TABLES",
])
def test_consultas_rechazadas(consulta):
    assert sql.validar_consulta(consulta)[0]


def test_el_punto_y_coma_final_se_quita():
    assert sql.validar_consulta("SELECT 1 ;")[1] == "SELECT 1"


# ------------------------------------------------------------- ejecucion
def test_la_base_es_de_solo_lectura(engine):
    # Aunque alguien se saltara el validador, la sesion no deja escribir.
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    with pytest.raises(SQLAlchemyError):
        with engine.connect() as con:
            con.execute(text("DELETE FROM orders"))


def test_error_real_del_motor(engine):
    v = sql.corregir_sql(engine, "SELECT order_statu FROM orders", "SELECT 1")
    assert v["estado"] == "error" and "order_statu" in v["error"]


def test_resultado_correcto_aunque_cambie_el_orden(engine):
    ref = "SELECT order_id, order_status FROM orders ORDER BY order_id"
    usr = "SELECT order_id, order_status FROM orders ORDER BY order_id DESC"
    assert sql.corregir_sql(engine, usr, ref)["estado"] == "ok"


def test_orden_importa_si_el_ejercicio_lo_pide(engine):
    ref = "SELECT order_id FROM orders ORDER BY order_id"
    usr = "SELECT order_id FROM orders ORDER BY order_id DESC"
    v = sql.corregir_sql(engine, usr, ref, ordenado=True)
    assert v["estado"] == "fallo" and "orden" in v["mensajes"][0]
    assert sql.corregir_sql(engine, ref, ref, ordenado=True)["estado"] == "ok"


def test_numero_de_columnas_y_filas(engine):
    ref = "SELECT order_id, order_status FROM orders"
    assert "1 columna" in sql.corregir_sql(engine, "SELECT order_id FROM orders", ref)["mensajes"][0]
    v = sql.corregir_sql(engine, "SELECT order_id, order_status FROM orders LIMIT 5", ref)
    assert "5 fila" in v["mensajes"][0]


def test_los_nombres_de_columna_solo_cuentan_con_alias(engine):
    ref = "SELECT COUNT(*) AS total FROM orders"
    usr = "SELECT COUNT(*) FROM orders"
    assert sql.corregir_sql(engine, usr, ref)["estado"] == "ok"
    v = sql.corregir_sql(engine, usr, ref, alias=True)
    assert v["estado"] == "fallo" and "AS" in v["mensajes"][0]


def test_filas_distintas_no_revelan_la_fila_esperada(engine):
    ref = "SELECT order_id, 1 AS x FROM orders"
    usr = "SELECT order_id, 2 AS x FROM orders"
    v = sql.corregir_sql(engine, usr, ref)
    assert v["estado"] == "fallo" and "no es correcta" in " ".join(v["mensajes"])


def test_decimales_y_floats_se_comparan_con_redondeo(engine):
    ref = "SELECT ROUND(AVG(price), 2) FROM order_items"
    usr = "SELECT ROUND(AVG(price), 2) AS media FROM order_items"
    assert sql.corregir_sql(engine, usr, ref)["estado"] == "ok"


def test_funciones_mysql_de_compatibilidad_en_el_fixture(engine):
    r = sql.ejecutar_consulta(engine, "SELECT YEAR(order_purchase_timestamp) FROM orders LIMIT 1")
    assert r.filas[0][0] in (2017, 2018)


def test_esquema(engine):
    esquema = sql.listar_esquema(engine)
    assert "order_items" in esquema and "price" in esquema["order_items"]


def test_url_mysql_sin_credenciales(monkeypatch):
    monkeypatch.setattr(sql.config, "DB_USER", None)
    assert sql.url_mysql() is None
    with pytest.raises(ValueError):
        sql.crear_engine()


def test_la_url_codifica_caracteres_raros_en_la_contrasena(monkeypatch):
    monkeypatch.setattr(sql.config, "DB_USER", "practicador")
    monkeypatch.setattr(sql.config, "DB_PASSWORD", "p@ss:w/ord#1")
    url = sql.url_mysql()
    assert url.password == "p@ss:w/ord#1"
    assert "p%40ss" in url.render_as_string(hide_password=False)
