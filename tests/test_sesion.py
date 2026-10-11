from datetime import datetime, timedelta

import pytest

from motor import sesion
from motor.banco import Banco, Ejercicio, Tema
from motor.niveles import siguiente_ejercicio
from motor.progreso import Progreso
from motor.sesion import ItemSesion, armar_sesion


class Reloj:
    def __init__(self):
        self.ahora = datetime.fromisoformat("2026-10-12 10:00:00")

    def __call__(self):
        return self.ahora

    def dias(self, n):
        self.ahora += timedelta(days=n)


def e(i, tema="t1", nivel="basico", tipo="python", cuenta=True):
    return Ejercicio(id=i, tipo=tipo, tema=tema, concepto=f"c-{i}", nivel=nivel, titulo=f"Titulo {i}",
                     enunciado="e", origen="o", cuenta_nivel=cuenta)


def banco_con(*ejercicios, temas=("t1", "t2")):
    return Banco(temas={t: Tema(t, t, orden=n) for n, t in enumerate(temas)},
                 ejercicios={x.id: x for x in ejercicios})


@pytest.fixture()
def reloj():
    return Reloj()


@pytest.fixture()
def prog(tmp_path, reloj):
    return Progreso(tmp_path / "p.db", reloj=reloj)


def ids(items):
    return [i.ejercicio_id for i in items]


def motivos(items):
    return [i.motivo for i in items]


# ------------------------------------------------------------------ estimacion
def test_estimacion_de_minutos_por_tipo_y_nivel():
    assert sesion.minutos_estimados(e("a")) == 4
    assert sesion.minutos_estimados(e("a", nivel="intermedio")) == 7
    assert sesion.minutos_estimados(e("a", nivel="junior")) == 10
    assert sesion.minutos_estimados(e("a", tipo="excel")) == 7
    assert sesion.minutos_estimados(e("a", tipo="test", nivel="junior", cuenta=False)) == 1


# ----------------------------------------------------------------- armar sesion
def test_sin_historial_son_dos_ejercicios_nuevos_de_temas_distintos():
    banco = banco_con(e("a1", "t1"), e("a2", "t1"), e("b1", "t2"))
    items = armar_sesion(banco, Progreso(":memory:"))
    assert ids(items) == ["a1", "b1"] and motivos(items) == ["nuevo", "nuevo"]


def test_si_hay_un_solo_tema_el_segundo_nuevo_sale_del_mismo_tema():
    banco = banco_con(e("a1"), e("a2"), e("a3"), temas=("t1",))
    assert ids(armar_sesion(banco, Progreso(":memory:"))) == ["a1", "a2"]


def test_empieza_por_el_ultimo_tema_practicado(prog):
    banco = banco_con(e("a1", "t1"), e("b1", "t2"), e("b2", "t2"))
    prog.registrar_intento(banco.ejercicios["b1"], False)
    assert ids(armar_sesion(banco, prog))[0] == "b1"


def test_los_repasos_vencidos_van_primero_y_se_mezclan_con_los_nuevos(prog, reloj):
    banco = banco_con(e("r1"), e("r2"), e("n1", "t2"), e("n2", "t2"))
    for r in ("r1", "r2"):
        prog.registrar_solucion_vista(banco.ejercicios[r])
    reloj.dias(1)
    items = armar_sesion(banco, prog)
    assert ids(items) == ["r1", "n1", "r2", "n2"]
    assert motivos(items) == ["repaso", "nuevo", "repaso", "nuevo"]


def test_un_repaso_que_aun_no_toca_no_entra_ni_se_ofrece_como_nuevo(prog):
    banco = banco_con(e("r1"), e("n1", "t2"), temas=("t1", "t2"))
    prog.registrar_solucion_vista(banco.ejercicios["r1"])      # toca manana
    items = armar_sesion(banco, prog)
    assert "r1" not in ids(items)
    assert ids(items) == ["n1"]


def test_el_orden_de_los_repasos_es_del_mas_atrasado_al_mas_reciente(prog, reloj):
    banco = banco_con(e("a"), e("b"), e("c"))
    prog.registrar_solucion_vista(banco.ejercicios["b"])
    reloj.dias(1)
    prog.registrar_solucion_vista(banco.ejercicios["a"])
    reloj.dias(3)
    assert ids(armar_sesion(banco, prog, max_nuevos=0)) == ["b", "a"]


def test_los_repasos_se_recortan_al_tiempo_pero_siempre_cabe_un_nuevo(prog, reloj):
    # 6 repasos de 7 min (intermedio) no caben en 20 min; el primer nuevo va reservado
    repasos = [e(f"r{i}", nivel="intermedio") for i in range(6)]
    banco = banco_con(*repasos, e("n1", "t2"), e("n2", "t2"))
    for r in repasos:
        prog.registrar_solucion_vista(r)
    reloj.dias(1)
    items = armar_sesion(banco, prog)
    assert motivos(items).count("nuevo") == 1                   # el segundo nuevo ya no cabe
    assert motivos(items).count("repaso") == 2                  # 7 + 7 + 4 (nuevo) = 18
    assert sesion.minutos_totales(banco, items) <= 20


def test_siempre_entra_al_menos_un_repaso_aunque_se_pase_del_tiempo(prog, reloj):
    largo = e("r1", nivel="junior", tipo="excel")               # 13 min
    banco = banco_con(largo, e("n1", "t2", nivel="junior"))     # 10 min
    prog.registrar_solucion_vista(largo)
    reloj.dias(1)
    assert ids(armar_sesion(banco, prog)) == ["r1", "n1"]


def test_sin_nuevos_los_repasos_llenan_la_sesion(prog, reloj):
    repasos = [e(f"r{i}") for i in range(7)]                    # 7 x 4 min
    banco = banco_con(*repasos, temas=("t1",))
    for r in repasos:
        prog.registrar_solucion_vista(r)
        prog.registrar_intento(r, True)                         # mismo dia: no avanza, pero hay que aprenderlos
    reloj.dias(1)
    items = armar_sesion(banco, prog)
    assert len(items) == 5 and set(motivos(items)) == {"repaso"}


def test_si_lo_has_aprendido_todo_y_no_hay_repasos_la_sesion_esta_vacia(prog):
    banco = banco_con(e("a"), e("b"), temas=("t1",))
    for x in ("a", "b"):
        prog.registrar_intento(banco.ejercicios[x], True)
    assert armar_sesion(banco, prog) == []


def test_las_preguntas_rapidas_no_se_ofrecen_como_ejercicios_nuevos():
    banco = banco_con(e("q1", tipo="test", cuenta=False), e("a1"), temas=("t1",))
    assert ids(armar_sesion(banco, Progreso(":memory:"))) == ["a1"]


def test_una_pregunta_rapida_fallada_si_se_repasa(prog, reloj):
    q = e("q1", tipo="test", cuenta=False)
    banco = banco_con(q, e("a1"), temas=("t1",))
    prog.registrar_solucion_vista(q)
    reloj.dias(1)
    assert ids(armar_sesion(banco, prog)) == ["q1", "a1"]


def test_un_ejercicio_que_ya_no_esta_en_el_banco_se_ignora(prog, reloj):
    from types import SimpleNamespace
    prog.registrar_solucion_vista(SimpleNamespace(id="borrado", tema="t1", concepto="x", nivel="basico"))
    reloj.dias(1)
    banco = banco_con(e("a1"), temas=("t1",))
    assert ids(armar_sesion(banco, prog)) == ["a1"]


# ----------------------------------------------------------- recorrer la sesion
ITEMS = [ItemSesion("a", "repaso"), ItemSesion("b", "nuevo"), ItemSesion("c", "repaso")]


def test_posicion_y_siguiente():
    assert sesion.posicion(ITEMS, "b") == 1 and sesion.posicion(ITEMS, "zzz") is None
    assert sesion.siguiente_en_sesion(ITEMS, "a") == "b"
    assert sesion.siguiente_en_sesion(ITEMS, "c") is None
    assert sesion.siguiente_en_sesion(ITEMS, "zzz") is None


def test_primer_pendiente():
    assert sesion.primer_pendiente(ITEMS, set()) == "a"
    assert sesion.primer_pendiente(ITEMS, {"a"}) == "b"
    assert sesion.primer_pendiente(ITEMS, {"a", "b", "c"}) is None


def test_resumen():
    r = sesion.resumen(ITEMS, {"a", "b"})
    assert r == {"total": 3, "hechos": 2, "repasos_hechos": 1, "nuevos_hechos": 1, "sin_hacer": ["c"]}


# ------------------------------------------------------- siguiente_ejercicio
def test_siguiente_ejercicio_admite_un_conjunto_de_exclusiones():
    banco = banco_con(e("a1"), e("a2"), e("a3"), temas=("t1",))
    assert siguiente_ejercicio(banco, "t1", set(), excluir="a1").id == "a2"
    assert siguiente_ejercicio(banco, "t1", set(), excluir={"a1", "a2"}).id == "a3"
    assert siguiente_ejercicio(banco, "t1", set(), excluir={"a1", "a2", "a3"}) is None
