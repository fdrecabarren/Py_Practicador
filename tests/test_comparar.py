import numpy as np
import pandas as pd

from motor.comparar import comparar, vista_previa


def test_escalares_iguales_y_distintos():
    assert comparar(5, 5) == []
    assert comparar(np.int64(5), 5) == []
    assert comparar(5.0, 5) == []  # 5 y 5.0 se aceptan como el mismo numero
    assert comparar(6, 5)
    assert comparar("hola", "hola") == []
    assert comparar("hola", "adios")


def test_floats_con_tolerancia():
    assert comparar(0.1 + 0.2, 0.3) == []
    assert comparar(0.31, 0.3)


def test_nan_se_considera_igual_a_nan():
    assert comparar(float("nan"), np.nan) == []
    assert comparar(None, np.nan) == []
    assert comparar(1, np.nan)


def test_bool_no_se_confunde_con_numero():
    assert comparar(True, True) == []
    assert comparar(1, True)
    assert comparar(True, 1)


def test_texto_casi_igual_da_pista_sin_revelar_el_esperado():
    msgs = comparar("Kenya ", "Kenya")
    assert msgs and "espacios" in " ".join(msgs)
    assert "Kenya'" not in " ".join(msgs).replace("Kenya '", "")  # no se imprime el valor esperado


def test_tipo_equivocado():
    assert "tipo" in comparar([1, 2], 3)[0]
    assert comparar(3, [1, 2])


def test_listas_orden_y_longitud():
    assert comparar([1, 2, 3], [1, 2, 3]) == []
    assert comparar([3, 2, 1], [1, 2, 3])
    assert comparar([3, 2, 1], [1, 2, 3], {"ignorar_orden_lista": True}) == []
    assert "3 elementos" in comparar([1, 2, 3], [1, 2])[0]


def test_conjuntos_aceptan_lista_sin_orden_ni_repetidos():
    assert comparar(["b", "a", "a"], {"a", "b"}) == []
    assert comparar(["a"], {"a", "b"})


def test_diccionarios():
    assert comparar({"a": 1, "b": 2}, {"b": 2, "a": 1}) == []
    assert comparar({"a": 1}, {"a": 1, "b": 2})
    assert comparar({"a": 9, "b": 2}, {"a": 1, "b": 2})
    assert comparar([1], {"a": 1})


def _df():
    return pd.DataFrame({"pais": ["KE", "PH", "PE"], "total": [10.0, 20.5, 5.25]})


def test_dataframe_igual_ignora_orden_filas_e_indice():
    otro = _df().sort_values("total").reset_index(drop=True)
    assert comparar(otro, _df()) == []
    assert comparar(_df().iloc[::-1], _df()) == []


def test_dataframe_orden_filas_importa_si_se_pide():
    inverso = _df().iloc[::-1]
    assert comparar(inverso, _df(), {"ignorar_orden_filas": False})


def test_dataframe_columnas_distintas():
    msgs = comparar(_df().rename(columns={"total": "suma"}), _df())
    texto = " ".join(msgs)
    assert "Faltan columnas" in texto and "Sobran columnas" in texto


def test_dataframe_orden_de_columnas_opcional():
    cambiado = _df()[["total", "pais"]]
    assert comparar(cambiado, _df()) == []
    assert comparar(cambiado, _df(), {"ignorar_orden_columnas": False})


def test_dataframe_numero_de_filas():
    assert "2 filas" in comparar(_df().head(2), _df())[0]


def test_dataframe_valor_distinto_no_revela_el_esperado():
    malo = _df()
    malo.loc[1, "total"] = 99.0
    msgs = comparar(malo, _df())
    assert msgs and "'total'" in msgs[0]
    assert "20.5" not in msgs[0]


def test_dataframe_tipo_de_columna_distinto():
    texto = _df().assign(total=lambda d: d["total"].astype(str))
    assert "tipo" in comparar(texto, _df())[0]


def test_dataframe_con_nulos():
    a = pd.DataFrame({"x": [1.0, np.nan, 3.0]})
    b = pd.DataFrame({"x": [1.0, np.nan, 3.0]})
    assert comparar(a, b) == []
    c = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    msgs = comparar(c, b)
    assert msgs and "nulos" in msgs[0]


def test_dataframe_fechas():
    a = pd.DataFrame({"f": pd.to_datetime(["2017-01-01", "2017-02-01"])})
    b = pd.DataFrame({"f": pd.to_datetime(["2017-02-01", "2017-01-01"])})
    assert comparar(a, b) == []
    assert comparar(a.assign(f=["2017-01-01", "2017-02-01"]), b)  # texto en vez de fecha


def test_series_con_indice():
    esperado = pd.Series([3, 2, 1], index=["a", "b", "c"])
    assert comparar(pd.Series([1, 2, 3], index=["c", "b", "a"]), esperado) == []
    assert comparar(pd.Series([3, 2, 1], index=["x", "y", "z"]), esperado)
    assert comparar(pd.Series([3, 2, 1], index=["x", "y", "z"]), esperado, {"ignorar_indice": True}) == []


def test_series_vs_dataframe_y_escalar():
    assert "Series" in comparar(_df(), pd.Series([1, 2, 3]))[0]
    assert "DataFrame" in comparar(3, _df())[0]
    assert comparar(pd.Series([1]), 3)


def test_vista_previa():
    assert "3 filas x 2 columnas" in vista_previa(_df())
    assert "Series de 3" in vista_previa(pd.Series([1, 2, 3]))
    assert vista_previa([1, 2]).startswith("list:")


def test_lista_esperada_acepta_array_e_index():
    assert comparar(np.array(["a", "b"]), ["a", "b"]) == []
    assert comparar(pd.Index(["a", "b"]), ["a", "b"]) == []
    assert comparar(pd.Series(["a", "b"]).unique(), ["a", "b"]) == []
    assert comparar(np.array(["a", "c"]), ["a", "b"])
