from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from motor.banco import Banco, Ejercicio, Tema
from motor.niveles import esta_bloqueado, estado_niveles, nivel_actual
from motor.progreso import Progreso


class Reloj:
    def __init__(self, inicio="2026-10-12 10:00:00"):
        self.ahora = datetime.fromisoformat(inicio)

    def __call__(self):
        return self.ahora

    def dias(self, n):
        self.ahora += timedelta(days=n)


def ej(i, nivel="basico", tema="pandas", concepto="isnull"):
    return SimpleNamespace(id=i, tema=tema, concepto=concepto, nivel=nivel)


@pytest.fixture()
def reloj():
    return Reloj()


@pytest.fixture()
def prog(tmp_path, reloj):
    return Progreso(tmp_path / "p.db", reloj=reloj)


# ------------------------------------------------------------- progreso
def test_acierto_directo_cuenta_como_aprendido(prog):
    r = prog.registrar_intento(ej("a"), True)
    assert r == {"aprendido": True, "aviso": None}
    assert prog.aprendidos() == {"a"}


def test_fallo_no_aprende_pero_cuenta_el_intento(prog):
    prog.registrar_intento(ej("a"), False)
    assert prog.aprendidos() == set()
    assert prog.num_intentos("a") == 1


def test_la_solucion_solo_se_puede_ver_tras_un_intento(prog):
    assert prog.puede_ver_solucion("a") is False
    prog.registrar_intento(ej("a"), False)
    assert prog.puede_ver_solucion("a") is True


def test_ver_la_solucion_deja_el_ejercicio_como_no_aprendido(prog):
    prog.registrar_intento(ej("a"), True)
    assert "a" in prog.aprendidos()
    prog.registrar_solucion_vista(ej("a"))
    assert "a" not in prog.aprendidos()
    assert prog.no_aprendidos() == ["a"]


def test_resolver_el_mismo_dia_tras_ver_la_solucion_no_cuenta(prog):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_solucion_vista(ej("a"))
    r = prog.registrar_intento(ej("a"), True)
    assert r["aprendido"] is False and "mañana" in r["aviso"]
    assert prog.aprendidos() == set()


def test_resolver_otro_dia_tras_ver_la_solucion_si_cuenta(prog, reloj):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_solucion_vista(ej("a"))
    reloj.dias(1)
    r = prog.registrar_intento(ej("a"), True)
    assert r["aprendido"] is True
    assert prog.aprendidos() == {"a"}
    assert prog.no_aprendidos() == []


def test_stats_por_concepto(prog):
    prog.registrar_intento(ej("a", concepto="isnull"), False)
    prog.registrar_intento(ej("a", concepto="isnull"), True)
    prog.registrar_intento(ej("b", concepto="fillna"), True)
    stats = {s["concepto"]: s for s in prog.stats_por_concepto()}
    assert stats["isnull"]["intentos"] == 2 and stats["isnull"]["aciertos"] == 1
    assert stats["fillna"]["aprendidos"] == 1


def test_racha_de_dias_seguidos(prog, reloj):
    assert prog.racha()["actual"] == 0
    prog.registrar_intento(ej("a"), True)
    reloj.dias(1)
    prog.registrar_intento(ej("b"), True)
    reloj.dias(1)
    prog.registrar_intento(ej("c"), True)
    assert prog.racha() == {"actual": 3, "mejor": 3, "total": 3, "hoy_practicado": True}
    reloj.dias(1)  # hoy aun no has practicado: la racha de ayer sigue viva
    assert prog.racha()["actual"] == 3 and prog.racha()["hoy_practicado"] is False
    reloj.dias(1)  # un dia entero sin practicar la rompe
    assert prog.racha()["actual"] == 0 and prog.racha()["mejor"] == 3


def test_el_progreso_persiste_entre_sesiones(tmp_path, reloj):
    p1 = Progreso(tmp_path / "p.db", reloj=reloj)
    p1.registrar_intento(ej("a"), True)
    p1.cerrar()
    assert Progreso(tmp_path / "p.db", reloj=reloj).aprendidos() == {"a"}


# --------------------------------------------------------------- niveles
def banco_con(n_basico=5, n_inter=5, n_junior=5):
    ejercicios = {}
    for nivel, n in (("basico", n_basico), ("intermedio", n_inter), ("junior", n_junior)):
        for i in range(n):
            e = Ejercicio(id=f"{nivel[:2]}{i}", tipo="python", tema="pandas", concepto="x", nivel=nivel,
                          titulo="t", enunciado="e", origen="o")
            ejercicios[e.id] = e
    t = Ejercicio(id="t1", tipo="test", tema="pandas", concepto="x", nivel="basico", titulo="t", enunciado="e",
                  origen="o", cuenta_nivel=False)
    ejercicios["t1"] = t
    return Banco(temas={"pandas": Tema("pandas", "pandas")}, ejercicios=ejercicios)


def test_nivel_se_supera_con_70_por_ciento():
    banco = banco_con()
    ap = {"ba0", "ba1", "ba2"}  # 3 de 5 = 60 %
    est = estado_niveles(banco, "pandas", ap)
    assert est[0].necesarios == 4 and not est[0].superado
    est = estado_niveles(banco, "pandas", ap | {"ba3"})  # 4 de 5 = 80 %
    assert est[0].superado


def test_un_nivel_exige_que_el_anterior_este_superado():
    banco = banco_con()
    todo_intermedio = {f"in{i}" for i in range(5)}
    est = estado_niveles(banco, "pandas", todo_intermedio)
    assert est[1].bloqueado and not est[1].superado  # basico no superado
    est = estado_niveles(banco, "pandas", todo_intermedio | {f"ba{i}" for i in range(4)})
    assert est[0].superado and est[1].superado and not est[2].bloqueado


def test_exactamente_70_por_ciento_es_suficiente():
    banco = banco_con(n_basico=10)
    est = estado_niveles(banco, "pandas", {f"ba{i}" for i in range(7)})
    assert est[0].superado


def test_nivel_actual_y_bloqueo_de_ejercicios():
    banco = banco_con()
    assert nivel_actual(estado_niveles(banco, "pandas", set())) == "basico"
    assert esta_bloqueado(banco, "in0", set()) is True
    assert esta_bloqueado(banco, "ba0", set()) is False
    assert esta_bloqueado(banco, "t1", set()) is False  # las preguntas test nunca se bloquean
    ap = {f"ba{i}" for i in range(4)}
    assert esta_bloqueado(banco, "in0", ap) is False
    assert nivel_actual(estado_niveles(banco, "pandas", ap)) == "intermedio"


def test_un_nivel_sin_ejercicios_no_bloquea():
    banco = banco_con(n_inter=0)
    est = estado_niveles(banco, "pandas", {f"ba{i}" for i in range(4)})
    assert est[1].total == 0 and est[1].superado and not est[2].bloqueado
