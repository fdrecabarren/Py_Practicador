"""Ejercicios de Excel y Power Query.

La app genera un .xlsx de partida (a partir de `hojas` del YAML), el alumno lo
resuelve en Excel y lo sube; aqui se lee con openpyxl y se comprueban celdas,
columnas, formulas y estructura. Solo se leen VALORES (no se compara texto de
formulas, salvo que la comprobacion pida que sea formula o que contenga algo).

Cosas a tener en cuenta (verificadas con el material del curso):
- Las formulas se guardan en el XML en INGLES y con coma (IF, SUMIFS), aunque
  Excel las muestre en espanol. Por eso `formula: SUMIFS` busca el nombre ingles.
- Los valores calculados solo existen si Excel guardo el archivo despues de
  recalcular (valor cacheado). Un xlsx escrito por Python no los tiene.
- Las fechas se guardan como numero de serie; aqui se convierten.
"""
from __future__ import annotations

import base64
import io
import re
import struct
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import ColorScaleRule, Rule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.utils.datetime import from_excel, to_excel
from openpyxl.worksheet.table import Table, TableStyleInfo

from . import config

MAX_BYTES = 15 * 1024 * 1024
TOLERANCIA = 0.01


class ErrorExcel(Exception):
    """El archivo subido no se puede leer o el ejercicio esta mal definido."""


# ===================================================================== datos
def _df_hoja(h: dict, dir_datos: Path) -> pd.DataFrame:
    """DataFrame con los datos de partida de una hoja (CSV de datos/ o filas en linea)."""
    if h.get("csv"):
        ruta = dir_datos / h["csv"]
        if not ruta.exists():
            raise ErrorExcel(f"Falta el dataset {h['csv']}. Ejecuta scripts/preparar_datos.py")
        df = pd.read_csv(ruta, sep=h.get("sep", ","), dtype=str, keep_default_na=False)
        if h.get("renombrar"):
            df = df.rename(columns=h["renombrar"])
        if h.get("consulta"):
            df = df.query(h["consulta"], engine="python")
        if h.get("elegir"):
            df = df[h["elegir"]]
        if h.get("n"):
            df = df.head(int(h["n"]))
        df = df.reset_index(drop=True)
        for col in h.get("numericas", []):
            df[col] = pd.to_numeric(df[col].str.strip())
        for col, formato in (h.get("fechas") or {}).items():
            df[col] = pd.to_datetime(df[col], format=formato)
        for col in h.get("vacias", []):
            df[col] = None
        return df
    return pd.DataFrame(h["filas"], columns=h["columnas"])


def datos_origen(ej, dir_datos: Path | None = None) -> dict[str, pd.DataFrame]:
    dir_datos = Path(dir_datos or config.DIR_DATOS)
    return {h["nombre"]: _df_hoja(h, dir_datos) for h in ej.hojas}


def _valor_excel(v):
    """Convierte un valor de pandas/numpy a algo que openpyxl sabe escribir."""
    if v is None:
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and v != v:
        return None
    return v


def construir_libro(ej, dir_datos: Path | None = None) -> Workbook:
    dfs = datos_origen(ej, dir_datos)
    wb = Workbook()
    wb.remove(wb.active)
    for h in ej.hojas:
        ws = wb.create_sheet(h["nombre"])
        df = dfs[h["nombre"]]
        f0 = int(h.get("fila_encabezado", 1))
        for j, col in enumerate(df.columns, start=1):
            c = ws.cell(row=f0, column=j, value=str(col))
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDE6F0")
        for i, fila in enumerate(df.itertuples(index=False), start=f0 + 1):
            for j, v in enumerate(fila, start=1):
                v = _valor_excel(v)
                c = ws.cell(row=i, column=j, value=v)
                if isinstance(v, datetime):
                    c.number_format = "dd/mm/yyyy hh:mm" if (v.hour or v.minute) else "dd/mm/yyyy"
                elif isinstance(v, date):
                    c.number_format = "dd/mm/yyyy"
        for ref, v in (h.get("celdas") or {}).items():
            ws[ref] = v
        for rango in h.get("combinar", []):
            ws.merge_cells(rango)
        for j, col in enumerate(df.columns, start=1):
            largo = max([len(str(col))] + [len(str(x)) for x in df.iloc[:200, j - 1]]) if len(df) else len(str(col))
            ws.column_dimensions[get_column_letter(j)].width = min(max(largo + 2, 10), 42)
        ws.freeze_panes = f"A{f0 + 1}"
    return wb


def generar_libro(ej, dir_datos: Path | None = None) -> bytes:
    buf = io.BytesIO()
    construir_libro(ej, dir_datos).save(buf)
    return buf.getvalue()


# ================================================================== calculos
_PERMITIDO = {
    "len": len, "sum": sum, "min": min, "max": max, "abs": abs, "round": round, "sorted": sorted,
    "list": list, "set": set, "dict": dict, "int": int, "float": float, "str": str, "range": range, "zip": zip,
    "enumerate": enumerate,
}


def evaluar(expr, datos: dict[str, pd.DataFrame]):
    """Evalua una expresion pandas del banco (`calc`) sobre los datos de partida."""
    try:
        entorno = {"__builtins__": {}, **_PERMITIDO, "datos": datos, "pd": pd, "np": np}
        res = eval(str(expr), entorno)  # noqa: S307 - expresiones del banco propio, sin builtins
    except Exception as exc:  # noqa: BLE001
        raise ErrorExcel(f"No se pudo evaluar calc {expr!r}: {exc}") from exc
    if isinstance(res, (pd.Series, np.ndarray, pd.Index)):
        res = [_valor_excel(x) for x in list(res)]
    elif isinstance(res, (list, tuple)):
        res = [_valor_excel(x) for x in res]
    else:
        res = _valor_excel(res)
    return res


def esperado_de(comprobacion: dict, datos: dict[str, pd.DataFrame]):
    if "calc" in comprobacion:
        return evaluar(comprobacion["calc"], datos)
    if "valores" in comprobacion:
        return comprobacion["valores"]
    return comprobacion.get("valor")


# ================================================================ comparacion
def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _como_fecha(v):
    """Devuelve datetime si v es fecha o numero de serie; None en otro caso."""
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if _numero(v):
        try:
            r = from_excel(v)
            return r if isinstance(r, datetime) else datetime(r.year, r.month, r.day)
        except Exception:  # noqa: BLE001
            return None
    return None


def razon_distinta(obtenido, esperado, tol: float = TOLERANCIA, ignorar_mayusculas: bool = False) -> str | None:
    """None si coinciden; si no, un codigo corto: vacio | texto | numero | fecha | distinto."""
    if esperado is None or (isinstance(esperado, str) and esperado == ""):
        return None if obtenido in (None, "") else "distinto"
    if obtenido is None or obtenido == "":
        return "vacio"
    if isinstance(esperado, bool):
        return None if (isinstance(obtenido, bool) and obtenido == esperado) else "distinto"
    if _numero(esperado):
        if isinstance(obtenido, bool):
            return "distinto"
        if _numero(obtenido):
            return None if abs(obtenido - esperado) <= max(tol, 1e-9 * abs(esperado)) else "distinto"
        if isinstance(obtenido, str):
            return "texto"
        return "distinto"
    if isinstance(esperado, (date, datetime)):
        e = _como_fecha(esperado)
        o = _como_fecha(obtenido)
        if o is None:
            return "texto" if isinstance(obtenido, str) else "distinto"
        if not isinstance(esperado, datetime) or (esperado.hour == 0 and esperado.minute == 0):
            return None if o.date() == e.date() else "distinto"
        return None if abs((o - e).total_seconds()) < 60 else "distinto"
    if isinstance(esperado, str):
        if not isinstance(obtenido, str):
            return "numero" if _numero(obtenido) else "distinto"
        a, b = (obtenido.casefold(), esperado.casefold()) if ignorar_mayusculas else (obtenido, esperado)
        return None if a == b else "distinto"
    return None if obtenido == esperado else "distinto"


def _clave(v, tol: float = TOLERANCIA):
    """Clave comparable para comparar listas sin importar el orden."""
    if v is None or v == "":
        return ("v",)
    if isinstance(v, bool):
        return ("b", v)
    if _numero(v):
        return ("n", round(float(v) / tol) if tol else float(v))
    d = _como_fecha(v) if isinstance(v, (date, datetime)) else None
    if d is not None:
        return ("f", d.isoformat())
    return ("s", str(v))


# ================================================================== el libro
class Libro:
    """Libro subido por el alumno, leido dos veces: formulas y valores guardados."""

    def __init__(self, contenido: bytes):
        if len(contenido) > MAX_BYTES:
            raise ErrorExcel("El archivo pesa demasiado (maximo 15 MB).")
        if not zipfile.is_zipfile(io.BytesIO(contenido)):
            raise ErrorExcel("Eso no parece un .xlsx. Guarda el libro en Excel como 'Libro de Excel (*.xlsx)'.")
        self.contenido = contenido
        try:
            self.f = load_workbook(io.BytesIO(contenido), data_only=False)
            self.v = load_workbook(io.BytesIO(contenido), data_only=True)
        except Exception as exc:  # noqa: BLE001
            raise ErrorExcel("No he podido abrir el archivo. ¿Está dañado, protegido con contraseña o no es un .xlsx de verdad? "
                             f"Detalle técnico: {exc}") from exc
        self.zip = zipfile.ZipFile(io.BytesIO(contenido))

    def nombres_hojas(self) -> list[str]:
        return list(self.f.sheetnames)

    def hoja(self, nombre: str):
        """(hoja con formulas, hoja con valores, nombre real) o None. Tolera mayusculas y espacios."""
        if nombre in self.f.sheetnames:
            return self.f[nombre], self.v[nombre], nombre
        norm = nombre.strip().casefold()
        for real in self.f.sheetnames:
            if real.strip().casefold() == norm:
                return self.f[real], self.v[real], real
        return None

    def archivos(self, patron: str) -> list[str]:
        return [n for n in self.zip.namelist() if re.fullmatch(patron, n)]


def _texto_formula(v) -> str | None:
    """Texto de la formula de una celda de openpyxl, o None si es un valor."""
    if isinstance(v, str) and v.startswith("=") and len(v) > 1:
        return v
    texto = getattr(v, "text", None)  # ArrayFormula
    if isinstance(texto, str):
        return texto if texto.startswith("=") else "=" + texto
    return None


def _celda(hoja, ref: str):
    """(valor guardado, texto de formula o None)."""
    wf, wv, _ = hoja
    return wv[ref].value, _texto_formula(wf[ref].value)


def _ultima_fila(ws) -> int:
    ultima = 0
    for fila in ws.iter_rows():
        for c in fila:
            if c.value not in (None, ""):
                ultima = max(ultima, c.row)
    return ultima


def _encabezado(hoja, nombre: str, fila: int = 1) -> int | None:
    """Indice de columna (desde 1) cuyo encabezado en `fila` coincide con `nombre`."""
    wv = hoja[1]
    objetivo = str(nombre).strip().casefold()
    for c in wv[fila]:
        if c.value is not None and str(c.value).strip().casefold() == objetivo:
            return c.column
    return None


def _formula_cumple(formula: str, requisito) -> bool:
    if requisito is True:
        return True
    return str(requisito).casefold() in formula.casefold()


# =============================================================== comprobaciones
def _res(ok: bool, titulo: str, mensaje: str = "", blando: bool = False) -> dict:
    return {"ok": ok, "titulo": titulo, "mensaje": "" if ok else mensaje, "blando": blando}


def _explicar(razon: str, obtenido) -> str:
    if razon == "vacio":
        return "La celda está vacía."
    if razon == "texto":
        return f"La celda contiene texto ({str(obtenido).strip()!r}), no un número. Mira el tipo de dato: un número se alinea a la derecha."
    if razon == "numero":
        return f"La celda contiene el número {obtenido}, pero se esperaba texto."
    return f"No tiene el valor esperado (ahora vale {_mostrar(obtenido)})."


def _mostrar(v) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M") if (v.hour or v.minute) else v.strftime("%d/%m/%Y")
    if isinstance(v, float):
        return f"{v:.6g}"
    return repr(v) if isinstance(v, str) else str(v)


def _titulo_celda(c: dict) -> str:
    return c.get("titulo") or f"Hoja «{c['hoja']}», celda {c['celda']}"


def _comp_celda(libro: Libro, c: dict, datos) -> dict:
    titulo = _titulo_celda(c)
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    obtenido, formula = _celda(hoja, c["celda"])
    if "formula" in c and c["formula"] is not False:
        if formula is None:
            return _res(False, titulo, f"Aquí hay un valor escrito a mano; el ejercicio pide una fórmula.{extra}")
        if not _formula_cumple(formula, c["formula"]):
            return _res(False, titulo, f"Hay una fórmula, pero no usa lo que pide el ejercicio ({c['formula']}).{extra}")
        for trozo in c.get("formula_contiene", []):
            if str(trozo).casefold() not in formula.casefold():
                return _res(False, titulo, f"La fórmula no contiene «{trozo}». Revisa las referencias.{extra}")
    if "valor" in c or "calc" in c:
        if formula is not None and obtenido is None:
            return _res(False, titulo, "La celda tiene fórmula pero el archivo no guarda su resultado. Ábrelo en Excel (no en la vista previa), "
                                       "deja que calcule y guárdalo con Ctrl+G.")
        esperado = esperado_de(c, datos)
        razon = razon_distinta(obtenido, esperado, c.get("tolerancia", TOLERANCIA), c.get("ignorar_mayusculas", False))
        if razon:
            return _res(False, titulo, _explicar(razon, obtenido) + extra)
    return _res(True, titulo)


def _valores_columna(hoja, col: int, fila_enc: int) -> tuple[list, list]:
    """(valores, formulas) de los datos bajo el encabezado, sin las filas vacias del final."""
    wf, wv, _ = hoja
    ultima = _ultima_fila(wv)
    valores, formulas = [], []
    for r in range(fila_enc + 1, ultima + 1):
        valores.append(wv.cell(row=r, column=col).value)
        formulas.append(_texto_formula(wf.cell(row=r, column=col).value))
    return valores, formulas


def _comp_columna(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or f"Hoja «{c['hoja']}», columna «{c['encabezado']}»"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    fila_enc = int(c.get("fila_encabezado", 1))
    col = _encabezado(hoja, c["encabezado"], fila_enc)
    if col is None:
        return _res(False, titulo, f"No encuentro una columna con el encabezado «{c['encabezado']}» en la fila {fila_enc}.{extra}")
    valores, formulas = _valores_columna(hoja, col, fila_enc)
    espera_contenido = any(k in c for k in ("formula", "valores", "calc", "solo_numeros"))
    if espera_contenido and not any(formulas) and all(v in (None, "") for v in valores):
        return _res(False, titulo, f"La columna «{c['encabezado']}» está vacía.{extra}")
    if "formula" in c and c["formula"] is not False:
        sin = [i for i, f in enumerate(formulas) if f is None and valores[i] not in (None, "")]
        if sin or not any(formulas):
            return _res(False, titulo, f"{len(sin) or len(valores)} celda(s) de la columna son valores escritos, no fórmulas "
                                       f"(la primera, en la fila {fila_enc + 1 + (sin[0] if sin else 0)}).{extra}")
        malas = [i for i, f in enumerate(formulas) if f is not None and not _formula_cumple(f, c["formula"])]
        if malas:
            return _res(False, titulo, f"La fórmula de la fila {fila_enc + 1 + malas[0]} no usa lo que pide el ejercicio ({c['formula']}).{extra}")
        for trozo in c.get("formula_contiene", []):
            faltan = [i for i, f in enumerate(formulas) if f is not None and str(trozo).casefold() not in f.casefold()]
            if faltan:
                return _res(False, titulo, f"La fórmula de la fila {fila_enc + 1 + faltan[0]} no contiene «{trozo}».{extra}")
        if any(f is not None and v is None for f, v in zip(formulas, valores)):
            return _res(False, titulo, "Hay fórmulas sin resultado guardado. Ábrelo en Excel (no en la vista previa), "
                                       "deja que calcule y guárdalo con Ctrl+G.")
    if c.get("solo_numeros"):
        no_num = [i for i, v in enumerate(valores) if v is not None and not _numero(v)]
        if no_num:
            return _res(False, titulo, f"{len(no_num)} celda(s) no son números (la primera, en la fila {fila_enc + 1 + no_num[0]}). "
                                       f"Un número se alinea a la derecha; el texto, a la izquierda.{extra}")
    if c.get("sin_vacios") and any(v in (None, "") for v in valores):
        i = next(i for i, v in enumerate(valores) if v in (None, ""))
        return _res(False, titulo, f"Hay celdas vacías (la primera, en la fila {fila_enc + 1 + i}).{extra}")
    if c.get("sin_espacios_extra"):
        mal = [i for i, v in enumerate(valores) if isinstance(v, str) and v != " ".join(v.split())]
        if mal:
            return _res(False, titulo, f"{len(mal)} celda(s) tienen espacios de más (la primera, en la fila {fila_enc + 1 + mal[0]}).{extra}")
    if c.get("sin_duplicados"):
        vistos = Counter(_clave(v) for v in valores if v not in (None, ""))
        if any(n > 1 for n in vistos.values()):
            return _res(False, titulo, f"Hay valores repetidos en la columna.{extra}")
    if "valores" in c or "calc" in c:
        esperado = esperado_de(c, datos)
        if not isinstance(esperado, list):
            esperado = [esperado]
        tol = c.get("tolerancia", TOLERANCIA)
        ign = c.get("ignorar_mayusculas", False)
        if c.get("orden", True):
            if len(valores) != len(esperado):
                return _res(False, titulo, f"La columna tiene {len(valores)} valores y se esperaban {len(esperado)}.{extra}")
            malas = [i for i, (o, e) in enumerate(zip(valores, esperado)) if razon_distinta(o, e, tol, ign)]
            if malas:
                i = malas[0]
                return _res(False, titulo, f"{len(malas)} celda(s) no tienen el valor esperado; la primera, en la fila {fila_enc + 1 + i} "
                                           f"(ahora vale {_mostrar(valores[i])}).{extra}")
        else:
            if len(valores) != len(esperado):
                return _res(False, titulo, f"La columna tiene {len(valores)} valores y se esperaban {len(esperado)}.{extra}")
            a, b = Counter(_clave(v, tol) for v in valores), Counter(_clave(v, tol) for v in esperado)
            if a != b:
                sobran = sum((a - b).values())
                return _res(False, titulo, f"{sobran} valor(es) de la columna no son los esperados (el número de filas sí coincide).{extra}")
    return _res(True, titulo)


def _comp_encabezados(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or f"Hoja «{c['hoja']}», encabezados"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    fila = int(c.get("fila_encabezado", 1))
    actuales = [str(x.value).strip() for x in hoja[1][fila] if x.value not in (None, "")]
    esperados = [str(x).strip() for x in c["valores"]]
    ok = actuales == esperados if c.get("orden", True) else sorted(actuales) == sorted(esperados)
    if ok:
        return _res(True, titulo)
    if len(actuales) != len(esperados):
        return _res(False, titulo, f"Hay {len(actuales)} columnas y se esperaban {len(esperados)}.{extra}")
    return _res(False, titulo, f"Los nombres o el orden de las columnas no coinciden con lo que pide el ejercicio "
                               f"(ahora: {', '.join(actuales)}).{extra}")


def _comp_hoja(libro: Libro, c: dict, datos) -> dict:
    nombre = c["hoja"]
    existe = libro.hoja(nombre) is not None
    quiere = c.get("existe", True)
    titulo = c.get("titulo") or (f"Existe la hoja «{nombre}»" if quiere else f"No existe la hoja «{nombre}»")
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    if existe == quiere:
        return _res(True, titulo)
    if quiere:
        return _res(False, titulo, f"No encuentro la hoja «{nombre}». Hojas del archivo: {', '.join(libro.nombres_hojas())}.{extra}")
    return _res(False, titulo, f"La hoja «{nombre}» no debería estar.{extra}")


def _comp_filas(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or f"Hoja «{c['hoja']}», número de filas de datos"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    fila_enc = int(c.get("fila_encabezado", 1))
    n = max(_ultima_fila(hoja[1]) - fila_enc, 0)
    esperado = esperado_de({**c, "valor": c.get("n")}, datos)
    if n == esperado:
        return _res(True, titulo)
    return _res(False, titulo, f"La hoja tiene {n} filas de datos y no son las esperadas.{extra}")


def _comp_tabla(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or f"Hoja «{c['hoja']}», datos convertidos en Tabla"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    tablas = list(hoja[0].tables.values())
    if not tablas:
        return _res(False, titulo, f"No hay ninguna Tabla de Excel (porque parezca una no lo es). Selecciona los datos y usa Insertar > Tabla.{extra}")
    if c.get("nombre") and not any(t.displayName.casefold() == str(c["nombre"]).casefold() for t in tablas):
        return _res(False, titulo, f"Hay una Tabla, pero no se llama «{c['nombre']}».{extra}")
    return _res(True, titulo)


def _comp_sin_combinadas(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or f"Hoja «{c['hoja']}», sin celdas combinadas"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    n = len(hoja[0].merged_cells.ranges)
    return _res(n == 0, titulo, f"Quedan {n} rango(s) de celdas combinadas. Descombínalas y repite el valor en cada fila.{extra}")


def _limites(rango: str) -> tuple[int, int, int, int]:
    """(col_min, fila_min, col_max, fila_max); una columna entera (C:C) abarca todas las filas."""
    c1, f1, c2, f2 = range_boundaries(rango)
    return c1 or 1, f1 or 1, c2 or 10**6, f2 or 10**7


def _cubre(sqref: str, rango: str) -> bool:
    """True si algun rango de `sqref` cubre por completo `rango`."""
    a = _limites(rango)
    for parte in str(sqref).split():
        b = _limites(parte)
        if b[0] <= a[0] and b[1] <= a[1] and b[2] >= a[2] and b[3] >= a[3]:
            return True
    return False


def _comp_formato_condicional(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or f"Hoja «{c['hoja']}», formato condicional «{c['regla']}» en {c['rango']}"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    hoja = libro.hoja(c["hoja"])
    if hoja is None:
        return _res(False, titulo, f"No encuentro la hoja «{c['hoja']}».{extra}")
    reglas = []
    for cf in hoja[0].conditional_formatting:
        for r in cf.rules:
            reglas.append((str(cf.sqref), r))
    if not reglas:
        return _res(False, titulo, f"La hoja no tiene ninguna regla de formato condicional.{extra}")
    for sqref, r in reglas:
        if r.type != c["regla"] or not _cubre(sqref, c["rango"]):
            continue
        if c.get("operador") and r.operator != c["operador"]:
            continue
        if c.get("valor") is not None:
            if not r.formula or str(r.formula[0]).strip('"') != str(c["valor"]).strip('"'):
                continue
        return _res(True, titulo)
    return _res(False, titulo, f"No encuentro esa regla aplicada a {c['rango']}. Reglas que sí hay: "
                               + "; ".join(f"{r.type} en {s}" for s, r in reglas) + f".{extra}")


def _xml_charts(libro: Libro) -> str:
    return "\n".join(libro.zip.read(n).decode("utf-8", "ignore") for n in libro.archivos(r"xl/charts/chart\d+\.xml"))


_TAG_GRAFICO = {"circular": "pieChart", "anillo": "doughnutChart", "barras": "barChart", "lineas": "lineChart",
                "dispersion": "scatterChart", "area": "areaChart"}


def _comp_grafico(libro: Libro, c: dict, datos) -> dict:
    tipo = c.get("tipo_grafico", "")
    titulo = c.get("titulo") or f"Hay un gráfico {tipo}".strip()
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    xml = _xml_charts(libro)
    if not xml:
        return _res(False, titulo, f"No encuentro ningún gráfico en el archivo.{extra}", c.get("blando", False))
    tag = _TAG_GRAFICO.get(tipo)
    if tag and not re.search(rf"<(?:\w+:)?{tag}\b", xml):
        return _res(False, titulo, f"Hay gráficos, pero ninguno de tipo {tipo}.{extra}", c.get("blando", False))
    et = c.get("etiquetas")
    if et == "porcentaje" and not re.search(r'showPercent val="1"', xml):
        return _res(False, titulo, f"Al gráfico le faltan las etiquetas de porcentaje.{extra}", c.get("blando", False))
    if et == "valor" and not re.search(r'showVal val="1"', xml):
        return _res(False, titulo, f"Al gráfico le faltan las etiquetas con el valor.{extra}", c.get("blando", False))
    return _res(True, titulo)


def _comp_tabla_dinamica(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or "Hay una tabla dinámica"
    ok = bool(libro.archivos(r"xl/pivotTables/pivotTable\d+\.xml"))
    return _res(ok, titulo, f"No encuentro ninguna tabla dinámica en el archivo. {c.get('mensaje', '')}".strip(), c.get("blando", False))


def _mashup(libro: Libro) -> list[bytes]:
    """Contenido binario de los DataMashup (consultas de Power Query) del archivo."""
    res = []
    for n in libro.archivos(r"customXml/item\d+\.xml"):
        datos = libro.zip.read(n)
        if b"DataMashup" in datos or "DataMashup".encode("utf-16-le") in datos:
            res.append(datos)
    return res


def codigo_m(libro: Libro) -> str:
    """Texto M de las consultas (mejor esfuerzo: formato [MS-QDEFF]); '' si no se puede leer."""
    texto = []
    for datos in _mashup(libro):
        try:
            xml = datos.decode("utf-16") if datos[:2] in (b"\xff\xfe", b"\xfe\xff") else datos.decode("utf-8-sig")
            b64 = re.search(r"<(?:\w+:)?DataMashup[^>]*>(.*?)</(?:\w+:)?DataMashup>", xml, re.S).group(1)
            bruto = base64.b64decode(b64.strip())
            (largo,) = struct.unpack("<I", bruto[4:8])
            with zipfile.ZipFile(io.BytesIO(bruto[8:8 + largo])) as z:
                for nombre in z.namelist():
                    if nombre.endswith(".m"):
                        texto.append(z.read(nombre).decode("utf-8-sig", "ignore"))
        except Exception:  # noqa: BLE001 - mejor esfuerzo
            continue
    return "\n".join(texto)


def _comp_power_query(libro: Libro, c: dict, datos) -> dict:
    titulo = c.get("titulo") or "El libro contiene una consulta de Power Query"
    extra = f" {c['mensaje']}" if c.get("mensaje") else ""
    blando = c.get("blando", False)
    if not _mashup(libro):
        return _res(False, titulo, f"No detecto ninguna consulta de Power Query en el archivo. Hazlo con Datos > Obtener datos > "
                                   f"Desde tabla o rango, y guarda el libro con la consulta.{extra}", blando)
    m = codigo_m(libro)
    for trozo in c.get("contiene_m", []):
        if trozo.casefold() not in m.casefold():
            return _res(False, titulo, f"La consulta no contiene «{trozo}». Revisa el paso del editor avanzado.{extra}", blando)
    return _res(True, titulo)


_COMPROBADORES = {
    "celda": _comp_celda, "columna": _comp_columna, "encabezados": _comp_encabezados, "hoja": _comp_hoja,
    "filas": _comp_filas, "tabla": _comp_tabla, "sin_combinadas": _comp_sin_combinadas,
    "formato_condicional": _comp_formato_condicional, "grafico": _comp_grafico,
    "tabla_dinamica": _comp_tabla_dinamica, "power_query": _comp_power_query,
}


def corregir_excel(ej, contenido: bytes, dir_datos: Path | None = None) -> dict:
    """Corrige un .xlsx. Devuelve {estado, comprobaciones, mensajes}.

    estado: ok | fallo | archivo_invalido | error_banco.
    Una comprobacion `blando: true` solo avisa: no impide dar el ejercicio por bueno.
    """
    try:
        libro = Libro(contenido)
    except ErrorExcel as exc:
        return {"estado": "archivo_invalido", "comprobaciones": [], "mensajes": [str(exc)]}
    try:
        datos = datos_origen(ej, dir_datos)
    except ErrorExcel as exc:
        return {"estado": "error_banco", "comprobaciones": [], "mensajes": [str(exc)]}
    comprobaciones = []
    for c in ej.comprobaciones:
        try:
            r = _COMPROBADORES[c["tipo"]](libro, c, datos)
        except ErrorExcel as exc:
            return {"estado": "error_banco", "comprobaciones": comprobaciones, "mensajes": [str(exc)]}
        except Exception as exc:  # noqa: BLE001
            return {"estado": "error_banco", "comprobaciones": comprobaciones,
                    "mensajes": [f"Fallo al comprobar {c.get('tipo')}: {type(exc).__name__}: {exc}"]}
        r["blando"] = r["blando"] or bool(c.get("blando"))
        comprobaciones.append(r)
    fallos = [r for r in comprobaciones if not r["ok"] and not r["blando"]]
    return {"estado": "fallo" if fallos else "ok", "comprobaciones": comprobaciones,
            "mensajes": [f"{r['titulo']}: {r['mensaje']}" for r in fallos]}


# ============================================== libro resuelto (solo validacion)
def _col_libre(ws, fila: int = 1) -> int:
    return max((c.column for c in ws[fila] if c.value is not None), default=0) + 1


def libro_resuelto(ej, dir_datos: Path | None = None) -> bytes:
    """Libro 'como lo dejaria Excel': aplica lo que piden las comprobaciones.

    Sirve para validar el banco (la solucion debe pasar) y para los tests. Las formulas
    llevan texto de ejemplo con el nombre de funcion que exige la comprobacion, y su
    valor guardado (cache), igual que un archivo guardado por Excel.
    """
    datos = datos_origen(ej, dir_datos)
    wb = construir_libro(ej, dir_datos)
    cache: list[tuple[str, str, str, object]] = []   # hoja, celda, formula, valor
    extras = {"grafico": [], "tabla_dinamica": False, "power_query": False, "m": []}

    def hoja(nombre):
        return wb[nombre] if nombre in wb.sheetnames else wb.create_sheet(nombre)

    def formula_de(c, defecto="A1"):
        f = c.get("ejemplo_formula")
        if f:
            return f if f.startswith("=") else "=" + f
        base = c["formula"] if isinstance(c.get("formula"), str) else "SUM"
        return f"={base}({defecto})" + "".join(f"+N({t})" for t in c.get("formula_contiene", []))

    for c in ej.comprobaciones:   # primero desombinar: no se puede escribir en una celda combinada
        if c["tipo"] == "sin_combinadas":
            ws = hoja(c["hoja"])
            for r in list(ws.merged_cells.ranges):
                ws.unmerge_cells(str(r))

    for c in ej.comprobaciones:
        t = c["tipo"]
        if t == "celda":
            ws = hoja(c["hoja"])
            ref = c["celda"]
            valor = esperado_de(c, datos) if ("valor" in c or "calc" in c) else None
            if c.get("formula"):
                f = formula_de(c)
                ws[ref] = f
                cache.append((c["hoja"], ref, f, valor))
            else:
                ws[ref] = valor
        elif t == "columna":
            ws = hoja(c["hoja"])
            fila_enc = int(c.get("fila_encabezado", 1))
            col = next((x.column for x in ws[fila_enc] if x.value is not None and str(x.value).strip().casefold()
                        == str(c["encabezado"]).strip().casefold()), None)
            if col is None:
                col = _col_libre(ws, fila_enc)
                ws.cell(row=fila_enc, column=col, value=c["encabezado"])
            if "valores" in c or "calc" in c:
                esperado = esperado_de(c, datos)
                esperado = esperado if isinstance(esperado, list) else [esperado]
                # un valor menos que filas previas: se limpia lo que sobre
                for r in range(fila_enc + 1, max(ws.max_row, fila_enc + len(esperado)) + 1):
                    ws.cell(row=r, column=col, value=None)
                for i, v in enumerate(esperado):
                    celda = ws.cell(row=fila_enc + 1 + i, column=col)
                    if c.get("formula"):
                        f = formula_de(c, defecto=f"A{fila_enc + 1 + i}")
                        celda.value = f
                        cache.append((c["hoja"], celda.coordinate, f, v))
                    else:
                        celda.value = v
            elif c.get("formula"):
                for r in range(fila_enc + 1, _ultima_fila(ws) + 1):
                    f = formula_de(c, defecto=f"A{r}")
                    ws.cell(row=r, column=col).value = f
                    cache.append((c["hoja"], ws.cell(row=r, column=col).coordinate, f, 1))
        elif t == "encabezados":
            ws = hoja(c["hoja"])
            for j, v in enumerate(c["valores"], start=1):
                ws.cell(row=int(c.get("fila_encabezado", 1)), column=j, value=v)
        elif t == "filas":
            ws = hoja(c["hoja"])
            fila_enc = int(c.get("fila_encabezado", 1))
            n = esperado_de({**c, "valor": c.get("n")}, datos)
            if ws.max_row - fila_enc != n:
                for r in range(fila_enc + 1, max(ws.max_row, fila_enc + n) + 1):
                    for col in range(1, ws.max_column + 1):
                        ws.cell(row=r, column=col, value=None)
                for r in range(fila_enc + 1, fila_enc + n + 1):
                    for col in range(1, max(ws.max_column, 1) + 1):
                        ws.cell(row=r, column=col, value="x")
        elif t == "hoja":
            if c.get("existe", True):
                hoja(c["hoja"])
            elif c["hoja"] in wb.sheetnames:
                del wb[c["hoja"]]
        elif t == "formato_condicional":
            ws = hoja(c["hoja"])
            if c["regla"] == "colorScale":
                ws.conditional_formatting.add(c["rango"], ColorScaleRule(start_type="min", start_color="FFFFFF",
                                                                         end_type="max", end_color="63BE7B"))
            else:
                regla = Rule(type=c["regla"], operator=c.get("operador"))
                if c.get("valor") is not None:
                    regla.formula = [str(c["valor"])]
                ws.conditional_formatting.add(c["rango"], regla)
        elif t == "grafico":
            extras["grafico"].append(c)
        elif t == "tabla_dinamica":
            extras["tabla_dinamica"] = True
        elif t == "power_query":
            extras["power_query"] = True
            extras["m"] += c.get("contiene_m", [])

    # Tablas de Excel: al final, cuando la hoja ya tiene su forma definitiva
    for c in ej.comprobaciones:
        if c["tipo"] == "tabla":
            ws = hoja(c["hoja"])
            ref = f"A1:{get_column_letter(max(ws.max_column, 1))}{max(ws.max_row, 2)}"
            nombre = re.sub(r"\W", "_", c.get("nombre") or f"Tabla_{c['hoja']}")
            tabla = Table(displayName=nombre, ref=ref)
            tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
            ws.add_table(tabla)

    buf = io.BytesIO()
    wb.save(buf)
    return _post_procesar(buf.getvalue(), wb.sheetnames, cache, extras)


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _post_procesar(contenido: bytes, hojas: list[str], cache, extras) -> bytes:
    """Escribe los valores guardados de las formulas y las estructuras que openpyxl no sabe crear."""
    entrada = zipfile.ZipFile(io.BytesIO(contenido))
    por_hoja: dict[str, dict[str, tuple[str, object]]] = {}
    for hoja, ref, formula, valor in cache:
        por_hoja.setdefault(hoja, {})[ref] = (formula, valor)

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for item in entrada.infolist():
            datos = entrada.read(item.filename)
            m = re.fullmatch(r"xl/worksheets/sheet(\d+)\.xml", item.filename)
            if m and por_hoja:
                nombre = hojas[int(m.group(1)) - 1]
                if nombre in por_hoja:
                    datos = _poner_cache(datos.decode("utf-8"), por_hoja[nombre]).encode("utf-8")
            z.writestr(item, datos)
        for i, g in enumerate(extras["grafico"], start=1):
            tag = _TAG_GRAFICO.get(g.get("tipo_grafico", ""), "barChart")
            et = ""
            if g.get("etiquetas") == "porcentaje":
                et = '<c:dLbls><c:showPercent val="1"/></c:dLbls>'
            elif g.get("etiquetas") == "valor":
                et = '<c:dLbls><c:showVal val="1"/></c:dLbls>'
            z.writestr(f"xl/charts/chart{i}.xml",
                       f'<?xml version="1.0"?><c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">'
                       f"<c:chart><c:plotArea><c:{tag}>{et}</c:{tag}></c:plotArea></c:chart></c:chartSpace>")
        if extras["tabla_dinamica"]:
            z.writestr("xl/pivotTables/pivotTable1.xml", '<?xml version="1.0"?><pivotTableDefinition name="TablaDinamica1"/>')
        if extras["power_query"]:
            z.writestr("customXml/item1.xml", _datamashup_sintetico("\n".join(extras["m"])))
    return salida.getvalue()


def _poner_cache(xml: str, celdas: dict[str, tuple[str, object]]) -> str:
    """Inserta <v> tras las <f> de las celdas indicadas (como hace Excel al guardar)."""
    def sustituir(m: re.Match) -> str:
        ref = m.group("ref")
        if ref not in celdas:
            return m.group(0)
        _, valor = celdas[ref]
        atributos = re.sub(r'\s+t="[^"]*"', "", m.group("attrs"))
        if valor is None:
            return f'<c r="{ref}"{atributos}>{m.group("f")}</c>'
        if isinstance(valor, bool):
            return f'<c r="{ref}"{atributos} t="b">{m.group("f")}<v>{int(valor)}</v></c>'
        if isinstance(valor, (datetime, date)):
            valor = to_excel(valor)
        if _numero(valor):
            return f'<c r="{ref}"{atributos}>{m.group("f")}<v>{valor!r}</v></c>'
        return f'<c r="{ref}"{atributos} t="str">{m.group("f")}<v>{_xml_escape(str(valor))}</v></c>'

    patron = re.compile(r'<c r="(?P<ref>[A-Z]+\d+)"(?P<attrs>[^>]*)>(?P<f><f>.*?</f>|<f[^>]*/>|<f [^>]*>.*?</f>)(?:<v\s*/>|<v></v>)?</c>', re.S)
    return patron.sub(sustituir, xml)


def _datamashup_sintetico(m: str) -> str:
    """customXml/item1.xml con un DataMashup minimo (formato [MS-QDEFF]) para validar el banco."""
    paquete = io.BytesIO()
    with zipfile.ZipFile(paquete, "w") as z:
        z.writestr("Formulas/Section1.m", m or "section Section1;")
    partes = paquete.getvalue()
    bruto = struct.pack("<II", 0, len(partes)) + partes + struct.pack("<III", 0, 0, 0)
    return ('<?xml version="1.0" encoding="utf-8"?><DataMashup xmlns="http://schemas.microsoft.com/DataMashup">'
            + base64.b64encode(bruto).decode("ascii") + "</DataMashup>")


def sin_calcular(contenido: bytes) -> bytes:
    """Version sin valores guardados (como un xlsx escrito por Python): solo para pruebas."""
    wb = load_workbook(io.BytesIO(contenido))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
