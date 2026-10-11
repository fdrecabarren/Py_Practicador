import importlib.util
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parent.parent / "scripts" / "preparar_datos.py"


@pytest.fixture
def prep(tmp_path, monkeypatch):
    """Carga scripts/preparar_datos.py apuntando datos y origen a una carpeta temporal."""
    spec = importlib.util.spec_from_file_location("preparar_datos_prueba", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    datos = tmp_path / "datos"
    datos.mkdir()
    origen = tmp_path / "origen.csv"
    origen.write_text("a;b\n1;2\n", encoding="utf-8")
    monkeypatch.setattr(modulo, "DIR_DATOS", datos)
    monkeypatch.setattr(modulo, "CUSTOMER", origen)
    return modulo, datos, origen


def test_crea_el_dataset_que_falta(prep):
    modulo, datos, origen = prep
    modulo.customer()
    assert (datos / "customer_activity.csv").read_text(encoding="utf-8") == origen.read_text(encoding="utf-8")


def test_no_pisa_un_dataset_existente_sin_forzar(prep, capsys):
    modulo, datos, _ = prep
    destino = datos / "customer_activity.csv"
    destino.write_text("el del repositorio\n", encoding="utf-8")
    modulo.customer()
    assert destino.read_text(encoding="utf-8") == "el del repositorio\n"
    assert "ya existe" in capsys.readouterr().out


def test_forzar_regenera_el_dataset(prep):
    modulo, datos, origen = prep
    destino = datos / "customer_activity.csv"
    destino.write_text("el del repositorio\n", encoding="utf-8")
    modulo.customer(forzar=True)
    assert destino.read_text(encoding="utf-8") == origen.read_text(encoding="utf-8")


def test_con_todo_presente_no_hace_falta_el_material_del_curso(prep, monkeypatch, capsys):
    """Un companero sin la carpeta del curso no debe ver avisos si los CSV ya estan."""
    modulo, datos, _ = prep
    for nombre in ("kiva_muestra.csv", "olist_ventas.csv", "olist_pedidos.csv",
                   "olist_vendedores.csv", "customer_activity.csv"):
        (datos / nombre).write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(modulo, "KIVA_COMPLETO", datos / "no_existe_1.csv")
    monkeypatch.setattr(modulo, "KIVA_REDUCIDO", datos / "no_existe_2.csv")
    monkeypatch.setattr(modulo, "OLIST_OUT", datos / "no_existe_3")
    modulo.main()
    salida = capsys.readouterr().out
    assert "AVISO" not in salida
    assert salida.count("ya existe") == 5
