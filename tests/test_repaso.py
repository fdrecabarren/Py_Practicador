import sqlite3
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from motor import repaso
from motor.progreso import ESQUEMA_V1, Progreso


class Reloj:
    def __init__(self, inicio="2026-10-12 10:00:00"):
        self.ahora = datetime.fromisoformat(inicio)

    def __call__(self):
        return self.ahora

    def dias(self, n):
        self.ahora += timedelta(days=n)


def ej(i, tema="pandas", concepto="isnull", nivel="basico"):
    return SimpleNamespace(id=i, tema=tema, concepto=concepto, nivel=nivel)


@pytest.fixture()
def reloj():
    return Reloj()


@pytest.fixture()
def prog(tmp_path, reloj):
    return Progreso(tmp_path / "p.db", reloj=reloj)


def cola(prog, ej_id="a"):
    fila = prog.en_cola(ej_id)
    return None if fila is None else (fila["etapa"], fila["proxima"])


D0 = date(2026, 10, 12)


# ------------------------------------------------------------ calendario puro
def test_el_calendario_es_1_3_y_7_dias():
    assert repaso.INTERVALOS_DIAS == (1, 3, 7)
    assert [repaso.fecha_repaso(D0, e) for e in range(3)] == [D0 + timedelta(days=n) for n in (1, 3, 7)]


def test_tras_el_ultimo_acierto_se_sale_de_la_cola():
    assert repaso.etapa_tras_acierto(0) == 1
    assert repaso.etapa_tras_acierto(1) == 2
    assert repaso.etapa_tras_acierto(2) is None


def test_etiquetas_de_etapa():
    assert [repaso.etiqueta_etapa(e) for e in range(3)] == ["1 día", "3 días", "7 días"]


def test_texto_de_cuando_toca():
    hoy = D0
    assert repaso.texto_proximo(hoy - timedelta(days=1), hoy) == "vencido hace 1 día"
    assert repaso.texto_proximo(hoy - timedelta(days=4), hoy) == "vencido hace 4 días"
    assert repaso.texto_proximo(hoy, hoy) == "toca hoy"
    assert repaso.texto_proximo(hoy + timedelta(days=1), hoy) == "mañana"
    assert repaso.texto_proximo(hoy + timedelta(days=5), hoy) == "en 5 días (17/10)"


# ------------------------------------------------------------- como se entra
def test_ver_la_solucion_mete_el_ejercicio_en_la_cola_para_manana(prog):
    prog.registrar_intento(ej("a"), False)
    assert prog.en_cola("a") is None
    prog.registrar_solucion_vista(ej("a"))
    assert cola(prog) == (0, D0 + timedelta(days=1))


def test_un_fallo_suelto_no_mete_en_la_cola(prog):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_intento(ej("a"), False)
    assert prog.en_cola("a") is None


def test_tres_fallos_seguidos_meten_en_la_cola(prog):
    for _ in range(3):
        prog.registrar_intento(ej("a"), False)
    assert cola(prog) == (0, D0 + timedelta(days=1))


def test_un_acierto_corta_la_racha_de_fallos(prog):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_intento(ej("a"), False)
    prog.registrar_intento(ej("a"), True)
    prog.registrar_intento(ej("a"), False)
    assert prog.en_cola("a") is None


def test_los_fallos_de_otros_ejercicios_no_cuentan(prog):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_intento(ej("b"), False)
    prog.registrar_intento(ej("a"), False)
    prog.registrar_intento(ej("b"), False)
    assert prog.en_cola("a") is None and prog.en_cola("b") is None


# ----------------------------------------------------------------- el ciclo
def test_ciclo_completo_1_3_7_y_sale_de_la_cola(prog, reloj):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_solucion_vista(ej("a"))              # dia 0
    assert cola(prog) == (0, D0 + timedelta(days=1))
    reloj.dias(1)                                       # dia 1: toca el primer repaso
    assert [r["ejercicio_id"] for r in prog.repasos_vencidos()] == ["a"]
    assert prog.registrar_intento(ej("a"), True)["aprendido"] is True
    assert cola(prog) == (1, D0 + timedelta(days=4))    # +3 dias
    reloj.dias(3)                                       # dia 4
    prog.registrar_intento(ej("a"), True)
    assert cola(prog) == (2, D0 + timedelta(days=11))   # +7 dias
    reloj.dias(7)                                       # dia 11
    prog.registrar_intento(ej("a"), True)
    assert prog.en_cola("a") is None
    assert prog.repasos_vencidos() == []


def test_acertar_un_repaso_con_retraso_avanza_desde_hoy(prog, reloj):
    prog.registrar_solucion_vista(ej("a"))
    reloj.dias(6)                                       # tocaba el dia 1, llega el dia 6
    prog.registrar_intento(ej("a"), True)
    assert cola(prog) == (1, D0 + timedelta(days=6 + 3))


def test_acertar_antes_de_que_toque_no_adelanta_el_calendario(prog, reloj):
    prog.registrar_solucion_vista(ej("a"))
    reloj.dias(1)
    prog.registrar_intento(ej("a"), True)               # etapa 1, toca el dia 4
    reloj.dias(1)                                       # dia 2: aun no toca
    prog.registrar_intento(ej("a"), True)
    assert cola(prog) == (1, D0 + timedelta(days=4))


def test_fallar_un_repaso_vuelve_a_empezar_desde_manana(prog, reloj):
    prog.registrar_solucion_vista(ej("a"))
    reloj.dias(1)
    prog.registrar_intento(ej("a"), True)               # etapa 1
    reloj.dias(3)                                       # dia 4: toca
    prog.registrar_intento(ej("a"), False)
    assert cola(prog) == (0, D0 + timedelta(days=5))


def test_fallar_antes_de_que_toque_no_reinicia(prog, reloj):
    prog.registrar_solucion_vista(ej("a"))
    reloj.dias(1)
    prog.registrar_intento(ej("a"), True)               # etapa 1, toca el dia 4
    reloj.dias(1)
    prog.registrar_intento(ej("a"), False)
    assert cola(prog) == (1, D0 + timedelta(days=4))


def test_ver_la_solucion_en_un_repaso_reinicia_la_etapa(prog, reloj):
    prog.registrar_solucion_vista(ej("a"))
    reloj.dias(1)
    prog.registrar_intento(ej("a"), True)               # etapa 1
    reloj.dias(3)
    prog.registrar_solucion_vista(ej("a"))
    assert cola(prog) == (0, D0 + timedelta(days=5))


def test_acertar_el_mismo_dia_que_viste_la_solucion_no_avanza(prog):
    prog.registrar_intento(ej("a"), False)
    prog.registrar_solucion_vista(ej("a"))
    r = prog.registrar_intento(ej("a"), True)
    assert r["aprendido"] is False
    assert cola(prog) == (0, D0 + timedelta(days=1))


# ------------------------------------------------------------------ consultas
def test_repasos_vencidos_salen_en_orden_y_solo_los_de_hoy_o_antes(prog, reloj):
    prog.registrar_solucion_vista(ej("b"))              # dia 0 -> toca el 1
    reloj.dias(1)
    prog.registrar_solucion_vista(ej("a"))              # dia 1 -> toca el 2
    assert [r["ejercicio_id"] for r in prog.repasos_vencidos()] == ["b"]
    reloj.dias(1)                                       # dia 2
    assert [r["ejercicio_id"] for r in prog.repasos_vencidos()] == ["b", "a"]
    assert [r["ejercicio_id"] for r in prog.repasos_programados()] == ["b", "a"]


def test_las_filas_de_repaso_traen_las_fechas_como_date(prog):
    prog.registrar_solucion_vista(ej("a", tema="sql", concepto="JOIN"))
    fila = prog.repasos_programados()[0]
    assert fila["proxima"] == D0 + timedelta(days=1) and isinstance(fila["proxima"], date)
    assert fila["tema"] == "sql" and fila["concepto"] == "JOIN" and fila["etapa"] == 0


def test_reiniciar_borra_tambien_los_repasos(prog):
    prog.registrar_solucion_vista(ej("a"))
    prog.reiniciar()
    assert prog.repasos_programados() == []


def test_intentos_por_dia_incluye_los_dias_sin_practica(prog, reloj):
    prog.registrar_intento(ej("a"), True)
    prog.registrar_intento(ej("a"), False)
    reloj.dias(2)
    prog.registrar_intento(ej("b"), True)
    serie = prog.intentos_por_dia(4)
    assert [s["dia"] for s in serie] == [D0 - timedelta(days=1) + timedelta(days=i) for i in range(4)]
    assert [(s["intentos"], s["aciertos"]) for s in serie] == [(0, 0), (2, 1), (0, 0), (1, 1)]


# ----------------------------------------------------------------- migracion
def test_la_migracion_desde_v1_conserva_datos_y_apunta_lo_pendiente(tmp_path, reloj):
    ruta = tmp_path / "viejo.db"
    con = sqlite3.connect(ruta)
    con.executescript(ESQUEMA_V1)
    con.execute("PRAGMA user_version = 1")
    con.execute("INSERT INTO ejercicios_estado(ejercicio_id, tema, concepto, nivel, aprendido, solucion_vista_dia, "
                "primer_dia, ultimo_dia, intentos, aciertos) VALUES ('a','pandas','isnull','basico',0,'2026-10-10','2026-10-10','2026-10-10',2,0)")
    con.execute("INSERT INTO ejercicios_estado(ejercicio_id, tema, concepto, nivel, aprendido, solucion_vista_dia, "
                "primer_dia, ultimo_dia, intentos, aciertos) VALUES ('b','pandas','fillna','basico',1,NULL,'2026-10-10','2026-10-10',1,1)")
    con.commit()
    con.close()

    prog = Progreso(ruta, reloj=reloj)
    assert prog.con.execute("PRAGMA user_version").fetchone()[0] == 2
    assert prog.aprendidos() == {"b"}                                   # nada se pierde
    fila = prog.en_cola("a")
    assert fila["etapa"] == 0 and fila["proxima"] == date(2026, 10, 11)  # vista el 10 -> tocaba el 11
    assert prog.en_cola("b") is None                                    # el aprendido no entra
    assert [r["ejercicio_id"] for r in prog.repasos_vencidos()] == ["a"]
