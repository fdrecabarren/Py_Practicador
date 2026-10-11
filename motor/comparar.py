"""Comparador de resultados: compara VALORES, no texto de codigo.

`comparar(usuario, esperado, opciones)` devuelve una lista de problemas en espanol.
Lista vacia = resultado correcto. Los mensajes describen que falla, pero no revelan
los valores esperados (solo el valor tuyo), para que el ejercicio siga siendo un reto.

Funciona con o sin pandas: solo usa pandas si el codigo del alumno ya lo ha importado.
"""
from __future__ import annotations

import math
import sys
from collections import Counter

OPCIONES_POR_DEFECTO = {
    "ignorar_orden_filas": True,     # pon False en ejercicios que piden ORDER BY / sort_values
    "ignorar_orden_columnas": True,
    "ignorar_indice": None,          # None = True en DataFrame, False en Series
    "ignorar_orden_lista": False,
    "ignorar_mayusculas": False,
    "ignorar_espacios_extremos": False,
    "tolerancia": 1e-6,
}


def _mod(nombre):
    return sys.modules.get(nombre)


def _opc(opciones):
    opc = dict(OPCIONES_POR_DEFECTO)
    opc.update(opciones or {})
    return opc


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def nombre_tipo(valor) -> str:
    pd = _mod("pandas")
    if pd is not None:
        if isinstance(valor, pd.DataFrame):
            return "DataFrame"
        if isinstance(valor, pd.Series):
            return "Series"
    return type(valor).__name__


def _a_python(valor):
    """Convierte escalares de numpy a escalares de Python."""
    np = _mod("numpy")
    if np is not None and isinstance(valor, np.generic):
        return valor.item()
    return valor


def _es_nulo(valor) -> bool:
    if valor is None:
        return True
    pd = _mod("pandas")
    if pd is not None:
        try:
            r = pd.isna(valor)
            return bool(r) if not hasattr(r, "__len__") else False
        except (TypeError, ValueError):
            return False
    return isinstance(valor, float) and math.isnan(valor)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _iguales_escalares(a, b, opc) -> bool:
    a, b = _a_python(a), _a_python(b)
    if _es_nulo(a) or _es_nulo(b):
        return _es_nulo(a) and _es_nulo(b)
    if isinstance(b, bool) or isinstance(a, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _es_numero(a) and _es_numero(b):
        return math.isclose(a, b, rel_tol=opc["tolerancia"], abs_tol=opc["tolerancia"])
    if isinstance(a, str) and isinstance(b, str):
        if opc["ignorar_espacios_extremos"]:
            a, b = a.strip(), b.strip()
        if opc["ignorar_mayusculas"]:
            a, b = a.lower(), b.lower()
        return a == b
    try:
        return bool(a == b)
    except (TypeError, ValueError):
        return False


def vista_previa(valor, max_filas: int = 10) -> str:
    """Texto corto para ensenar al alumno lo que ha devuelto su codigo."""
    pd = _mod("pandas")
    try:
        if pd is not None and isinstance(valor, pd.DataFrame):
            cab = f"DataFrame de {valor.shape[0]} filas x {valor.shape[1]} columnas"
            return cab + "\n" + valor.head(max_filas).to_string(max_colwidth=40)
        if pd is not None and isinstance(valor, pd.Series):
            cab = f"Series de {len(valor)} elementos (dtype: {valor.dtype})"
            return cab + "\n" + valor.head(max_filas).to_string()
        texto = repr(valor)
    except Exception as exc:  # una vista previa nunca debe romper la correccion
        return f"<no se pudo mostrar el resultado: {exc}>"
    if len(texto) > 1500:
        texto = texto[:1500] + " ..."
    return f"{type(valor).__name__}: {texto}"


# ----------------------------------------------------------------------------
# Comparacion principal
# ----------------------------------------------------------------------------
def comparar(usuario, esperado, opciones=None) -> list[str]:
    opc = _opc(opciones)
    pd = _mod("pandas")

    if pd is not None and isinstance(esperado, pd.DataFrame):
        if not isinstance(usuario, pd.DataFrame):
            return [f"Se esperaba un DataFrame y tu resultado es de tipo {nombre_tipo(usuario)}."]
        return _comparar_df(usuario, esperado, opc)

    if pd is not None and isinstance(esperado, pd.Series):
        if not isinstance(usuario, pd.Series):
            return [f"Se esperaba una Series y tu resultado es de tipo {nombre_tipo(usuario)}."]
        return _comparar_series(usuario, esperado, opc)

    if pd is not None and isinstance(usuario, (pd.DataFrame, pd.Series)):
        return [f"Tu resultado es un {nombre_tipo(usuario)}, pero aquí se esperaba un valor de tipo {nombre_tipo(esperado)}."]

    if isinstance(esperado, dict):
        return _comparar_dict(usuario, esperado, opc)

    if isinstance(esperado, (set, frozenset)):
        if not isinstance(usuario, (set, frozenset, list, tuple)):
            return [f"Se esperaba un conjunto o lista y tu resultado es de tipo {nombre_tipo(usuario)}."]
        return _comparar_conjunto(list(usuario), list(esperado), opc)

    if isinstance(esperado, (list, tuple)):
        np, pd_ = _mod("numpy"), _mod("pandas")
        if np is not None and isinstance(usuario, np.ndarray):
            usuario = usuario.tolist()
        elif pd_ is not None and isinstance(usuario, (pd_.Index, pd_.api.extensions.ExtensionArray)):
            usuario = list(usuario)
        if not isinstance(usuario, (list, tuple)):
            return [f"Se esperaba una lista y tu resultado es de tipo {nombre_tipo(usuario)}."]
        return _comparar_lista(list(usuario), list(esperado), opc)

    return _comparar_escalar(usuario, esperado, opc)


def _comparar_escalar(usuario, esperado, opc) -> list[str]:
    usuario, esperado = _a_python(usuario), _a_python(esperado)
    if isinstance(usuario, (list, tuple, dict, set)) or nombre_tipo(usuario) in ("DataFrame", "Series"):
        return [f"Tu resultado es de tipo {nombre_tipo(usuario)}, pero aquí se esperaba un valor simple ({nombre_tipo(esperado)})."]
    if _iguales_escalares(usuario, esperado, opc):
        return []
    tipo_u, tipo_e = nombre_tipo(usuario), nombre_tipo(esperado)
    es_num_u = _es_numero(usuario)
    es_num_e = _es_numero(esperado)
    if es_num_u != es_num_e or (isinstance(usuario, bool) != isinstance(esperado, bool)):
        return [f"Tu resultado es de tipo {tipo_u} y se esperaba {tipo_e}. Tu valor: {usuario!r}."]
    if isinstance(usuario, str) and isinstance(esperado, str):
        pistas = []
        if usuario.strip() == esperado.strip() and usuario != esperado:
            pistas.append("Casi: hay espacios sobrantes al principio o al final.")
        elif usuario.lower() == esperado.lower():
            pistas.append("Casi: el texto coincide salvo mayúsculas y minúsculas.")
        return [f"El texto no coincide. Tu valor: {usuario!r}."] + pistas
    return [f"El valor no coincide. Tu resultado: {usuario!r}."]


def _comparar_lista(usuario, esperado, opc) -> list[str]:
    if len(usuario) != len(esperado):
        return [f"Tu lista tiene {len(usuario)} elementos y se esperaban {len(esperado)}."]
    if opc["ignorar_orden_lista"]:
        return _comparar_conjunto(usuario, esperado, opc, multiconjunto=True)
    for i, (u, e) in enumerate(zip(usuario, esperado)):
        if comparar(u, e, opc):
            return [f"El elemento en la posición {i} no coincide (tu valor: {u!r})."]
    return []


def _clave_hash(valor):
    valor = _a_python(valor)
    if isinstance(valor, float):
        return round(valor, 6)
    if isinstance(valor, (list, tuple)):
        return tuple(_clave_hash(v) for v in valor)
    try:
        hash(valor)
        return valor
    except TypeError:
        return repr(valor)


def _comparar_conjunto(usuario, esperado, opc, multiconjunto=False) -> list[str]:
    cu = Counter(_clave_hash(v) for v in usuario)
    ce = Counter(_clave_hash(v) for v in esperado)
    if not multiconjunto:
        cu, ce = Counter(set(cu)), Counter(set(ce))
    if cu == ce:
        return []
    sobran = list((cu - ce).elements())
    faltan = list((ce - cu).elements())
    msgs = []
    if len(usuario) != len(esperado) and not multiconjunto:
        msgs.append(f"Tu resultado tiene {len(set(map(_clave_hash, usuario)))} valores distintos y se esperaban {len(set(map(_clave_hash, esperado)))}.")
    if sobran:
        msgs.append(f"Hay {len(sobran)} valor(es) que no deberían estar, por ejemplo {sobran[0]!r}.")
    if faltan:
        msgs.append(f"Faltan {len(faltan)} valor(es) esperados.")
    return msgs


def _comparar_dict(usuario, esperado, opc) -> list[str]:
    if not isinstance(usuario, dict):
        return [f"Se esperaba un diccionario y tu resultado es de tipo {nombre_tipo(usuario)}."]
    msgs = []
    sobran = [k for k in usuario if k not in esperado]
    faltan = [k for k in esperado if k not in usuario]
    if sobran:
        msgs.append(f"Hay claves que no deberían estar, por ejemplo {sobran[0]!r}.")
    if faltan:
        msgs.append(f"Faltan {len(faltan)} clave(s) esperadas.")
    for k in esperado:
        if k in usuario and comparar(usuario[k], esperado[k], opc):
            msgs.append(f"El valor de la clave {k!r} no coincide (tu valor: {usuario[k]!r}).")
            break
    return msgs


# ----------------------------------------------------------------------------
# pandas
# ----------------------------------------------------------------------------
def _familia(serie) -> str:
    pd = _mod("pandas")
    t = pd.api.types
    if isinstance(serie.dtype, pd.CategoricalDtype):
        return "texto"
    if t.is_bool_dtype(serie) or t.is_numeric_dtype(serie):
        return "numerico"
    if t.is_datetime64_any_dtype(serie):
        return "fecha"
    if t.is_timedelta64_dtype(serie):
        return "duracion"
    if t.is_string_dtype(serie):
        return "texto"
    return "objeto"


_NOMBRE_FAMILIA = {
    "numerico": "número",
    "fecha": "fecha (datetime)",
    "duracion": "duración (timedelta)",
    "texto": "texto",
    "objeto": "objeto",
}


def _comparar_df(usuario, esperado, opc) -> list[str]:
    pd = _mod("pandas")
    msgs: list[str] = []

    cols_u, cols_e = list(map(str, usuario.columns)), list(map(str, esperado.columns))
    if len(set(cols_u)) != len(cols_u):
        return ["Tu DataFrame tiene nombres de columna repetidos."]
    faltan = [c for c in cols_e if c not in cols_u]
    sobran = [c for c in cols_u if c not in cols_e]
    if faltan or sobran:
        if faltan:
            msgs.append(f"Faltan columnas: {faltan}.")
        if sobran:
            msgs.append(f"Sobran columnas: {sobran}.")
        msgs.append(f"Tus columnas: {cols_u}.")
        return msgs
    if not opc["ignorar_orden_columnas"] and cols_u != cols_e:
        return [f"Las columnas son las correctas pero van en otro orden. Tu orden: {cols_u}."]

    if len(usuario) != len(esperado):
        return [f"Tu resultado tiene {len(usuario)} filas y se esperaban {len(esperado)}."]

    u = usuario.copy()
    e = esperado.copy()
    u.columns, e.columns = cols_u, cols_e
    u = u[cols_e]

    ignorar_indice = opc["ignorar_indice"]
    ignorar_indice = True if ignorar_indice is None else ignorar_indice
    if not ignorar_indice:
        u.insert(0, "__indice__", list(u.index))
        e.insert(0, "__indice__", list(e.index))
    u, e = u.reset_index(drop=True), e.reset_index(drop=True)

    if opc["ignorar_orden_filas"] and len(e) > 1:
        clave = list(e.columns)
        try:
            u = u.sort_values(clave, kind="stable", na_position="last", ignore_index=True)
            e = e.sort_values(clave, kind="stable", na_position="last", ignore_index=True)
        except TypeError:
            u = u.astype(str).sort_values(clave, kind="stable", ignore_index=True)
            e = e.astype(str).sort_values(clave, kind="stable", ignore_index=True)

    for col in e.columns:
        problema = _comparar_columna(u[col], e[col], col, opc)
        if problema:
            msgs.append(problema)
    if msgs and opc["ignorar_orden_filas"] is False:
        msgs.append("Aquí el orden de las filas importa.")
    return msgs


def _comparar_columna(u, e, col, opc):
    pd = _mod("pandas")
    np = _mod("numpy")
    nombre = "los valores" if col == "valor" else f"la columna '{col}'"
    fam_u, fam_e = _familia(u), _familia(e)
    if fam_u != fam_e:
        return (f"{nombre.capitalize()} no tiene el tipo esperado: el tuyo es "
                f"{_NOMBRE_FAMILIA[fam_u]} ({u.dtype}) y se esperaba {_NOMBRE_FAMILIA[fam_e]}.")
    nulos_u, nulos_e = u.isna().to_numpy(), e.isna().to_numpy()
    if fam_e == "numerico":
        a = pd.to_numeric(u, errors="coerce").to_numpy(dtype="float64", na_value=np.nan)
        b = pd.to_numeric(e, errors="coerce").to_numpy(dtype="float64", na_value=np.nan)
        iguales = np.isclose(a, b, rtol=opc["tolerancia"], atol=opc["tolerancia"], equal_nan=True)
    elif fam_e in ("fecha", "duracion"):
        iguales = (u.to_numpy() == e.to_numpy()) | (nulos_u & nulos_e)
    else:
        lu, le = u.astype(object).tolist(), e.astype(object).tolist()
        iguales = np.array([
            (nu and ne) or (not nu and not ne and _iguales_escalares(x, y, opc))
            for x, y, nu, ne in zip(lu, le, nulos_u, nulos_e)
        ], dtype=bool)
    iguales = np.asarray(iguales, dtype=bool)
    if iguales.all():
        return None
    malas = int((~iguales).sum())
    ejemplo = u[~iguales].iloc[0]
    ej = "nulo" if _es_nulo(ejemplo) else repr(_a_python(ejemplo))
    extra = ""
    if int(nulos_u.sum()) != int(nulos_e.sum()):
        extra = f" Tu columna tiene {int(nulos_u.sum())} nulos y se esperaban {int(nulos_e.sum())}."
    return f"{nombre.capitalize()} tiene {malas} valor(es) distinto(s) de {len(u)}; por ejemplo, uno de los tuyos es {ej}.{extra}"


def _comparar_series(usuario, esperado, opc) -> list[str]:
    pd = _mod("pandas")
    if len(usuario) != len(esperado):
        return [f"Tu Series tiene {len(usuario)} elementos y se esperaban {len(esperado)}."]
    ignorar_indice = opc["ignorar_indice"]
    ignorar_indice = False if ignorar_indice is None else ignorar_indice
    fu = pd.DataFrame({"valor": usuario.to_numpy() if usuario.dtype != "category" else usuario.astype(object).to_numpy()})
    fe = pd.DataFrame({"valor": esperado.to_numpy() if esperado.dtype != "category" else esperado.astype(object).to_numpy()})
    if not ignorar_indice:
        fu.insert(0, "indice", list(usuario.index))
        fe.insert(0, "indice", list(esperado.index))
    opc2 = dict(opc, ignorar_indice=True)
    msgs = _comparar_df(fu, fe, opc2)
    return [m.replace("La columna 'indice'", "El índice") for m in msgs]
