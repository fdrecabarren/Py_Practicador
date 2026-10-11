import pytest

from motor.ejecutor_python import ejecutar_python as ejecutar


@pytest.fixture()
def datos(tmp_path):
    (tmp_path / "mini.csv").write_text("pais,monto\nKE,10\nPH,20\nPE,\n", encoding="utf-8")
    return tmp_path


SOL = "import pandas as pd\ndf = pd.read_csv('mini.csv')\nresultado = df['monto'].isnull().sum()"


def test_resultado_correcto(datos):
    r = ejecutar("import pandas as pd\ndf = pd.read_csv('mini.csv')\nresultado = int(df.monto.isna().sum())",
                 solucion=SOL, datos=["mini.csv"], dir_datos=datos)
    assert r["estado"] == "ok", r
    assert "int: 1" in r["vista"]


def test_resultado_incorrecto_da_mensaje(datos):
    r = ejecutar("resultado = 99", solucion=SOL, datos=["mini.csv"], dir_datos=datos)
    assert r["estado"] == "fallo"
    assert r["mensajes"]


def test_falta_la_variable_resultado(datos):
    r = ejecutar("x = 1", solucion=SOL, datos=["mini.csv"], dir_datos=datos)
    assert r["estado"] == "fallo"
    assert "resultado" in r["mensajes"][0]


def test_error_real_de_python_con_numero_de_linea(datos):
    r = ejecutar("import pandas as pd\ndf = pd.read_csv('mini.csv')\nresultado = df['no_existe']",
                 solucion=SOL, datos=["mini.csv"], dir_datos=datos)
    assert r["estado"] == "error"
    assert 'File "<tu_codigo>", line 3' in r["traceback"]
    assert "df['no_existe']" in r["traceback"]
    assert "KeyError: 'no_existe'" in r["traceback"]


def test_error_de_sintaxis(datos):
    r = ejecutar("print('hola'\nx = 1", solucion=SOL, dir_datos=datos)
    assert r["estado"] == "error"
    assert "SyntaxError" in r["traceback"]


def test_timeout(datos):
    r = ejecutar("while True:\n    pass", solucion="resultado = 1", timeout=2, dir_datos=datos)
    assert r["estado"] == "timeout"
    assert "2 segundos" in r["mensajes"][0]


def test_dataset_inexistente(datos):
    r = ejecutar("resultado = 1", solucion="resultado = 1", datos=["no_esta.csv"], dir_datos=datos)
    assert r["estado"] == "sin_datos"
    assert "preparar_datos" in r["mensajes"][0]


def test_solucion_de_referencia_rota_es_error_del_banco(datos):
    r = ejecutar("resultado = 1", solucion="resultado = 1 / 0", dir_datos=datos)
    assert r["estado"] == "error_banco"
    assert "ZeroDivisionError" in r["traceback"]


def test_test_de_funcion(datos):
    tests = [{"tipo": "funcion", "nombre": "doble", "casos": [{"args": [2], "esperado": 4}, {"args": [0], "esperado": 0}]}]
    ok = ejecutar("def doble(x):\n    return x * 2", tests=tests, dir_datos=datos)
    assert ok["estado"] == "ok", ok
    mal = ejecutar("def doble(x):\n    return x + 3", tests=tests, dir_datos=datos)
    assert mal["estado"] == "fallo"
    assert "doble(2)" in mal["mensajes"][0] and "esperaba 4" in mal["mensajes"][0]
    sin = ejecutar("x = 1", tests=tests, dir_datos=datos)
    assert sin["estado"] == "fallo" and "doble" in sin["mensajes"][0]


def test_funcion_que_lanza_excepcion(datos):
    tests = [{"tipo": "funcion", "nombre": "f", "casos": [{"args": [1], "esperado": 1}]}]
    r = ejecutar("def f(x):\n    return x / 0", tests=tests, dir_datos=datos)
    assert r["estado"] == "error"
    assert "ZeroDivisionError" in r["traceback"]


def test_test_de_salida_con_entrada_y_sin_importar_el_prompt(datos):
    tests = [{"tipo": "salida", "entrada": "3\n4\n", "esperado": "7"}]
    codigo = "a = int(input('Primer numero: '))\nb = int(input('Segundo: '))\nprint('Suma:', a + b)"
    r = ejecutar(codigo, tests=[dict(tests[0], esperado="Suma: 7")], dir_datos=datos)
    assert r["estado"] == "ok", r
    r2 = ejecutar("a = int(input())\nb = int(input())\nprint(a * b)", tests=tests, dir_datos=datos)
    assert r2["estado"] == "fallo"
    assert "12" in r2["mensajes"][0]


def test_salida_compara_numeros_no_texto(datos):
    tests = [{"tipo": "salida", "entrada": "", "esperado": "2.5"}]
    assert ejecutar("print(5 / 2.0)", tests=tests, dir_datos=datos)["estado"] == "ok"
    assert ejecutar("print('2.50')", tests=tests, dir_datos=datos)["estado"] == "ok"


def test_input_sin_datos_da_eof(datos):
    r = ejecutar("x = input()", tests=[{"tipo": "salida", "entrada": "", "esperado": ""}], dir_datos=datos)
    assert r["estado"] == "error" and "EOFError" in r["traceback"]


def test_modo_ejecutar_muestra_salida_y_resultado(datos):
    r = ejecutar("print('hola')\nresultado = [1, 2]", modo="ejecutar", dir_datos=datos)
    assert r["estado"] == "ok" and "hola" in r["stdout"] and "list" in r["vista"]


def test_el_proceso_hijo_no_ve_las_credenciales(datos, monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "secreto")
    r = ejecutar("import os\nprint(os.environ.get('DB_PASSWORD', 'no-visible'))", modo="ejecutar", dir_datos=datos)
    assert "no-visible" in r["stdout"] and "secreto" not in r["stdout"]


def test_el_codigo_corre_en_carpeta_temporal(datos):
    r = ejecutar("open('basura.txt', 'w').write('x')", modo="ejecutar", dir_datos=datos)
    assert r["estado"] == "ok"
    assert not (datos / "basura.txt").exists()
