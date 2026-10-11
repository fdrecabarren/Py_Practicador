import importlib.util
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from motor import config
from motor.banco import ErrorBanco, cargar_banco

_spec = importlib.util.spec_from_file_location("validar_banco", config.RAIZ / "scripts" / "validar_banco.py")
validar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validar)


# ------------------------------------------------------------ formato del banco
def _escribir(tmp_path: Path, ejercicios: list[dict]) -> Path:
    (tmp_path / "_temas.yaml").write_text(yaml.safe_dump([{"id": "pandas", "nombre": "pandas"}]), encoding="utf-8")
    (tmp_path / "x.yaml").write_text(yaml.safe_dump(ejercicios, allow_unicode=True), encoding="utf-8")
    return tmp_path


def _valido(**cambios) -> dict:
    base = {
        "id": "t-001", "tipo": "python", "tema": "pandas", "concepto": "c", "nivel": "basico", "titulo": "t",
        "enunciado": "e", "origen": "o", "solucion": "resultado = 1", "explicacion": "x",
        "pistas": ["a", "b", "c"],
    }
    base.update(cambios)
    return base


def test_un_ejercicio_valido_carga(tmp_path):
    banco = cargar_banco(_escribir(tmp_path, [_valido()]))
    assert "t-001" in banco.ejercicios


@pytest.mark.parametrize("cambios, texto", [
    ({"nivel": "experto"}, "nivel"),
    ({"tipo": "otro"}, "tipo"),
    ({"pistas": ["solo una"]}, "pistas"),
    ({"solucion": ""}, "solucion"),
    ({"explicacion": ""}, "explicacion"),
    ({"origen": ""}, "origen"),
    ({"tema": "inexistente"}, "tema"),
    ({"tests": [{"tipo": "funcion", "nombre": "f"}]}, "funcion"),
    ({"tests": [{"tipo": "salida"}]}, "salida"),
])
def test_los_ejercicios_mal_formados_se_rechazan_con_mensaje(tmp_path, cambios, texto):
    with pytest.raises(ErrorBanco) as exc:
        cargar_banco(_escribir(tmp_path, [_valido(**cambios)]))
    assert texto in str(exc.value)


def test_id_repetido(tmp_path):
    with pytest.raises(ErrorBanco, match="repetido"):
        cargar_banco(_escribir(tmp_path, [_valido(), _valido()]))


def test_pregunta_test_necesita_opciones_y_correcta(tmp_path):
    q = {"id": "q-1", "tipo": "test", "tema": "pandas", "concepto": "c", "nivel": "basico", "titulo": "t",
         "enunciado": "e", "origen": "o", "explicacion": "x", "opciones": ["a", "b"], "correcta": 5}
    with pytest.raises(ErrorBanco, match="correcta"):
        cargar_banco(_escribir(tmp_path, [q]))
    q["correcta"] = 1
    assert cargar_banco(_escribir(tmp_path, [q])).ejercicios["q-1"].cuenta_nivel is False


# ------------------------------------------------------------------ banco real
@pytest.fixture(scope="module")
def banco():
    return cargar_banco()


def test_el_banco_real_carga_y_esta_equilibrado(banco):
    por_tema = Counter((e.tema, e.nivel) for e in banco.ejercicios.values() if e.cuenta_nivel)
    for tema in ("python_basico", "pandas", "sql", "excel_pq", "terminal_git"):
        assert sum(n for (t, _), n in por_tema.items() if t == tema) >= 15
        for nivel in config.NIVELES:
            assert por_tema[(tema, nivel)] >= 3, (tema, nivel)
    assert sum(1 for e in banco.ejercicios.values() if e.tipo == "test") >= 25


def test_todos_los_ejercicios_tienen_origen_y_pistas(banco):
    for e in banco.ejercicios.values():
        assert e.origen.strip()
        if e.admite_pistas:
            assert len(e.pistas) == 3


@pytest.mark.skipif(not (config.DIR_DATOS / "kiva_muestra.csv").exists(),
                    reason="faltan los datasets: ejecuta scripts/preparar_datos.py")
def test_las_soluciones_python_pasan_sus_tests_y_el_codigo_inicial_no(banco):
    ejercicios = [e for e in banco.ejercicios.values() if e.tipo == "python"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(validar.validar_python, ejercicios))
    fallos = {e.id: f for e, (f, _) in zip(ejercicios, resultados) if f}
    assert not fallos, fallos


def test_las_soluciones_sql_funcionan_en_el_mini_olist(banco, tmp_path):
    from motor.fixture_olist import crear_fixture, engine_fixture
    engine = engine_fixture(crear_fixture(tmp_path / "olist.db"))
    ejercicios = [e for e in banco.ejercicios.values() if e.tipo == "sql"]
    fallos = {}
    for e in ejercicios:
        f, _ = validar.validar_sql(e, engine, "sqlite")
        if f:
            fallos[e.id] = f
    assert not fallos, fallos


# ------------------------------------------------------------------ fase 2: formato
def _excel_valido(**cambios) -> dict:
    base = {
        "id": "x-001", "tipo": "excel", "tema": "pandas", "concepto": "c", "nivel": "basico", "titulo": "t",
        "enunciado": "e", "origen": "o", "solucion": "pasos", "explicacion": "x", "pistas": ["a", "b", "c"],
        "nombre_archivo": "x.xlsx", "hojas": [{"nombre": "H", "columnas": ["a"], "filas": [[1]]}],
        "comprobaciones": [{"tipo": "celda", "hoja": "H", "celda": "A1", "valor": 1}],
    }
    base.update(cambios)
    return base


def test_un_ejercicio_de_excel_valido_carga(tmp_path):
    assert "x-001" in cargar_banco(_escribir(tmp_path, [_excel_valido()])).ejercicios


@pytest.mark.parametrize("cambios, texto", [
    ({"nombre_archivo": "x.csv"}, "nombre_archivo"),
    ({"hojas": []}, "hojas"),
    ({"hojas": [{"nombre": "H"}]}, "csv"),
    ({"comprobaciones": []}, "comprobaciones"),
    ({"comprobaciones": [{"tipo": "magia"}]}, "magia"),
    ({"comprobaciones": [{"tipo": "celda", "hoja": "H"}]}, "celda"),
    ({"comprobaciones": [{"tipo": "columna", "hoja": "H"}]}, "columna"),
    ({"solucion": ""}, "solucion"),
])
def test_excel_mal_formado_se_rechaza(tmp_path, cambios, texto):
    with pytest.raises(ErrorBanco) as exc:
        cargar_banco(_escribir(tmp_path, [_excel_valido(**cambios)]))
    assert texto in str(exc.value)


def _terminal_valido(**cambios) -> dict:
    base = {
        "id": "t-001", "tipo": "terminal_git", "tema": "pandas", "concepto": "c", "nivel": "basico", "titulo": "t",
        "enunciado": "e", "origen": "o", "solucion": "mkdir a", "explicacion": "x", "pistas": ["a", "b", "c"],
        "comprobaciones": [{"archivo": "a", "carpeta": True}],
    }
    base.update(cambios)
    return base


def test_un_ejercicio_de_terminal_valido_carga(tmp_path):
    e = cargar_banco(_escribir(tmp_path, [_terminal_valido(preparar="touch x", remoto=True)])).ejercicios["t-001"]
    assert e.preparar == "touch x" and e.remoto is True


@pytest.mark.parametrize("cambios, texto", [
    ({"comprobaciones": []}, "comprobaciones"),
    ({"comprobaciones": [{"archivo": "a", "git": "status", "igual": ""}]}, "uno solo"),
    ({"comprobaciones": [{"titulo": "sin nada"}]}, "uno solo"),
    ({"comprobaciones": [{"git": "status"}]}, "criterio"),
    ({"solucion": ""}, "solucion"),
])
def test_terminal_mal_formado_se_rechaza(tmp_path, cambios, texto):
    with pytest.raises(ErrorBanco) as exc:
        cargar_banco(_escribir(tmp_path, [_terminal_valido(**cambios)]))
    assert texto in str(exc.value)


# ------------------------------------------------------------------ fase 2: banco real
@pytest.mark.skipif(not (config.DIR_DATOS / "kiva_muestra.csv").exists(),
                    reason="faltan los datasets: ejecuta scripts/preparar_datos.py")
def test_los_ejercicios_de_excel_pasan_la_validacion(banco):
    ejercicios = [e for e in banco.ejercicios.values() if e.tipo == "excel"]
    assert len(ejercicios) >= 15
    fallos = {}
    for e in ejercicios:
        f, _ = validar.validar_excel(e)
        if f:
            fallos[e.id] = f
    assert not fallos, fallos


@pytest.mark.skipif(not (config.DIR_DATOS / "kiva_muestra.csv").exists(),
                    reason="faltan los datasets: ejecuta scripts/preparar_datos.py")
def test_los_ejercicios_de_excel_no_filtran_la_funcion_en_la_pista_1(banco):
    for e in (x for x in banco.ejercicios.values() if x.tipo == "excel"):
        _, avisos = validar.validar_excel(e)
        assert not [a for a in avisos if "pista 1" in a], (e.id, avisos)


def test_los_ejercicios_de_terminal_pasan_la_validacion(banco):
    from motor import terminal
    if terminal.encontrar_bash() is None or terminal.encontrar_git() is None:
        pytest.skip("hace falta Git for Windows")
    ejercicios = [e for e in banco.ejercicios.values() if e.tipo == "terminal_git"]
    assert len(ejercicios) >= 15
    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(validar.validar_terminal, ejercicios))
    fallos = {e.id: f for e, (f, _) in zip(ejercicios, resultados) if f}
    assert not fallos, fallos
