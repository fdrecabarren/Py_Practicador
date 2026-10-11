"""Pruebas de humo de la interfaz con AppTest de Streamlit (sin navegador)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from motor import config
from motor.banco import cargar_banco
from motor.progreso import Progreso

PAGINAS = ["paginas/inicio.py", "paginas/practicar.py", "paginas/progreso.py", "paginas/ajustes.py"]


def _app(pagina, **estado):
    at = AppTest.from_file(str(config.RAIZ / pagina), default_timeout=60)
    for k, v in estado.items():
        at.session_state[k] = v
    return at.run()


def _boton(at, etiqueta):
    return next(b for b in at.button if b.label == etiqueta)


@pytest.mark.parametrize("pagina", PAGINAS)
def test_las_paginas_cargan_sin_excepciones(pagina):
    at = _app(pagina)
    assert not at.exception, [e.value for e in at.exception]


def test_lista_de_practicar_muestra_todos_los_temas():
    at = _app("paginas/practicar.py")
    assert not at.exception
    assert [r.label for r in at.radio][0] == "Tema"
    assert len(at.radio[0].options) == 5


def test_comprobar_una_solucion_correcta_registra_el_acierto():
    banco = cargar_banco()
    ej = banco.ejercicios["pb-002"]
    at = _app("paginas/practicar.py", ejercicio_abierto="pb-002", **{"codigo:pb-002": ej.solucion})
    assert not at.exception
    _boton(at, "Comprobar").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Correcto" in s.value for s in at.success)
    assert "pb-002" in Progreso(config.DB_PROGRESO).aprendidos()


def test_comprobar_un_resultado_incorrecto_no_aprende_y_desbloquea_la_solucion():
    at = _app("paginas/practicar.py", ejercicio_abierto="pb-003")
    assert _boton(at, "Ver solución explicada").disabled is True
    _boton(at, "Comprobar").click()
    at.run()
    assert any("Todavía no" in e.value for e in at.error)
    assert "pb-003" not in Progreso(config.DB_PROGRESO).aprendidos()
    assert _boton(at, "Ver solución explicada").disabled is False


def test_error_de_python_muestra_el_traceback_real():
    at = _app("paginas/practicar.py", ejercicio_abierto="pb-005")
    _boton(at, "Comprobar").click()
    at.run()
    codigos = " ".join(c.value for c in at.code)
    assert "TypeError" in codigos and "<tu_codigo>" in codigos


def test_sql_sin_conexion_avisa_y_deshabilita_los_botones():
    at = _app("paginas/practicar.py", ejercicio_abierto="sq-001")
    assert not at.exception
    assert any(".env" in w.value for w in at.warning)
    assert _boton(at, "Comprobar").disabled is True


def test_pregunta_tipo_test():
    at = _app("paginas/practicar.py", ejercicio_abierto="pq-001")
    assert not at.exception
    at.radio[0].set_value(0).run()
    _boton(at, "Responder").click()
    at.run()
    assert any("Correcto" in s.value for s in at.success)
    assert "pq-001" in Progreso(config.DB_PROGRESO).aprendidos()


def test_un_ejercicio_bloqueado_no_se_abre():
    at = _app("paginas/practicar.py", ejercicio_abierto="pb-010")  # intermedio, con basico sin superar
    assert not at.exception
    assert any("bloqueado" in w.value.lower() for w in at.warning)


# ------------------------------------------------------------------ fase 2
def test_ejercicio_de_excel_se_abre_con_descarga_y_subida():
    at = _app("paginas/practicar.py", ejercicio_abierto="xl-001")
    assert not at.exception, [e.value for e in at.exception]
    assert any(b.label == "Comprobar" and b.disabled for b in at.button)       # sin archivo no se puede comprobar
    assert any("Tu archivo" in m.value for m in at.markdown)
    assert any("Ver solución explicada" == b.label and b.disabled for b in at.button)


def test_ejercicio_de_terminal_pide_preparar_y_luego_comprueba(tmp_path, monkeypatch):
    from motor import terminal
    if terminal.encontrar_bash() is None:
        pytest.skip("hace falta Git for Windows")
    monkeypatch.setattr(config, "DIR_SANDBOX", tmp_path / "sandbox")
    at = _app("paginas/practicar.py", ejercicio_abierto="tg-001")
    assert not at.exception, [e.value for e in at.exception]
    _boton(at, "Preparar ejercicio").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert terminal.esta_preparado("tg-001")
    _boton(at, "Comprobar").click()
    at.run()
    assert any("Todavía no" in e.value for e in at.error)
    assert "tg-001" not in Progreso(config.DB_PROGRESO).aprendidos()
    _boton(at, "Ver estado").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("ls -A" in c.value for c in at.code)
    # el alumno hace lo que pide el enunciado y vuelve a comprobar
    ej = cargar_banco().ejercicios["tg-001"]
    ok, salida = terminal.resolver(ej)
    assert ok, salida
    _boton(at, "Comprobar").click()
    at.run()
    assert any("Correcto" in s.value for s in at.success), [e.value for e in at.error]
    assert "tg-001" in Progreso(config.DB_PROGRESO).aprendidos()
