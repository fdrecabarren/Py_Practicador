"""Ejecucion y correccion de consultas SQL contra Olist (MySQL local).

Seguridad en capas (el alumno escribe SQL libre):
1. Solo se aceptan sentencias SELECT / WITH ... SELECT, una sola, sin palabras de escritura.
2. La sesion se abre en modo SOLO LECTURA (SET SESSION TRANSACTION READ ONLY) y con
   limite de tiempo (MAX_EXECUTION_TIME).
3. Recomendado: usar un usuario MySQL que solo tenga SELECT (scripts/usuario_mysql.sql).

La correccion compara el resultado de tu consulta con el de la consulta de referencia
del ejercicio ejecutada en ese momento sobre tus mismos datos.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from . import config

MAX_FILAS = 20000
PALABRAS_PROHIBIDAS = (
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke",
    "rename", "call", "load", "outfile", "dumpfile", "into", "lock", "unlock", "handler",
    "sleep", "benchmark", "shutdown", "kill", "install", "uninstall", "flush", "optimize",
)


# ------------------------------------------------------------------ conexion
def url_mysql() -> URL | None:
    """URL de conexion desde .env, o None si faltan credenciales."""
    if not config.DB_USER or config.DB_PASSWORD is None:
        return None
    return URL.create(
        "mysql+mysqlconnector",
        username=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=int(config.DB_PORT),
        database=config.DB_NAME,
    )


def crear_engine(url: URL | str | None = None) -> Engine:
    """Crea el engine en modo solo lectura. Sin `url`, usa las credenciales de .env."""
    url = url or url_mysql()
    if url is None:
        raise ValueError("Faltan DB_USER / DB_PASSWORD en el archivo .env")
    engine = create_engine(url, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _solo_lectura(dbapi_con, _registro):  # pragma: no cover - depende del motor
        cur = dbapi_con.cursor()
        if engine.dialect.name == "sqlite":
            cur.execute("PRAGMA query_only = ON")
        else:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME={config.TIMEOUT_SQL * 1000}")
        cur.close()

    return engine


def probar_conexion(engine: Engine) -> tuple[bool, str]:
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
        return True, "Conexión correcta."
    except SQLAlchemyError as exc:
        return False, _mensaje_error(exc)


def listar_esquema(engine: Engine) -> dict[str, list[str]]:
    insp = inspect(engine)
    return {t: [c["name"] for c in insp.get_columns(t)] for t in sorted(insp.get_table_names())}


def _mensaje_error(exc: Exception) -> str:
    """Error real del motor (MySQL / SQLite), sin el volcado de SQLAlchemy."""
    orig = getattr(exc, "orig", None)
    return str(orig if orig is not None else exc).strip()


# ---------------------------------------------------------------- validacion
def _esqueleto(sql: str) -> tuple[str, str]:
    """Devuelve (sql_sin_comentarios, esqueleto) donde el esqueleto tiene el contenido de
    los textos entre comillas vaciado. Sirve para buscar palabras y ';' sin falsos positivos."""
    limpio, esq = [], []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c in "'\"`":
            j = i + 1
            while j < n:
                if sql[j] == "\\" and c != "`":
                    j += 2
                    continue
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:  # comilla doblada
                        j += 2
                        continue
                    break
                j += 1
            trozo = sql[i:j + 1]
            limpio.append(trozo)
            esq.append(c + c if c != "`" else "`x`")
            i = j + 1
        elif sql.startswith("--", i) or c == "#":
            j = sql.find("\n", i)
            i = n if j == -1 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            limpio.append(" ")
            esq.append(" ")
        else:
            limpio.append(c)
            esq.append(c)
            i += 1
    return "".join(limpio), "".join(esq)


def validar_consulta(sql: str) -> tuple[str | None, str]:
    """Devuelve (mensaje_de_error_o_None, sql_limpio_sin_punto_y_coma_final)."""
    limpio, esq = _esqueleto(sql or "")
    limpio, esq = limpio.strip(), esq.strip()
    while esq.endswith(";"):
        limpio, esq = limpio[:-1].rstrip(), esq[:-1].rstrip()
    if not esq:
        return "Escribe una consulta SQL.", ""
    if ";" in esq:
        return "Escribe una sola sentencia (quita los ';' intermedios).", ""
    primera = re.match(r"\(*\s*([a-zA-Z]+)", esq)
    if not primera or primera.group(1).lower() not in ("select", "with"):
        return "Solo se permiten consultas que empiecen por SELECT o WITH.", ""
    for palabra in PALABRAS_PROHIBIDAS:
        if re.search(rf"\b{palabra}\b", esq, flags=re.IGNORECASE):
            return f"La palabra '{palabra.upper()}' no está permitida: aquí solo se consulta, no se modifica la base.", ""
    return None, limpio


# ---------------------------------------------------------------- ejecucion
@dataclass
class Resultado:
    columnas: list[str]
    filas: list[tuple]
    truncado: bool = False


def _normalizar(valor):
    if valor is None:
        return None
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date, time, timedelta)):
        return str(valor)
    if isinstance(valor, (bytes, bytearray)):
        return valor.decode("utf-8", errors="replace")
    return valor


def ejecutar_consulta(engine: Engine, sql: str, max_filas: int = MAX_FILAS) -> Resultado:
    """Ejecuta una consulta ya validada. Lanza SQLAlchemyError si el motor la rechaza."""
    with engine.connect() as con:
        r = con.execute(text(sql))
        columnas = list(r.keys())
        filas = [tuple(_normalizar(v) for v in fila) for fila in r.fetchmany(max_filas + 1)]
    truncado = len(filas) > max_filas
    return Resultado(columnas, filas[:max_filas], truncado)


# --------------------------------------------------------------- comparacion
def _clave_fila(fila: tuple) -> tuple:
    return tuple(round(v, 4) if isinstance(v, float) else v for v in fila)


def comparar_resultados(usuario: Resultado, esperado: Resultado, *, ordenado: bool = False, alias: bool = False) -> list[str]:
    if len(usuario.columnas) != len(esperado.columnas):
        return [f"Tu consulta devuelve {len(usuario.columnas)} columna(s) y se esperaban {len(esperado.columnas)}."]
    if alias:
        nu = [c.lower() for c in usuario.columnas]
        ne = [c.lower() for c in esperado.columnas]
        if nu != ne:
            return [f"Los nombres de las columnas deben ser {esperado.columnas} (los tuyos: {usuario.columnas}). Usa AS."]
    if len(usuario.filas) != len(esperado.filas):
        return [f"Tu consulta devuelve {len(usuario.filas)} fila(s) y se esperaban {len(esperado.filas)}."]

    ku = [_clave_fila(f) for f in usuario.filas]
    ke = [_clave_fila(f) for f in esperado.filas]
    if Counter(ku) == Counter(ke):
        if ordenado and ku != ke:
            return ["Las filas son las correctas, pero el orden no: este ejercicio pide un ORDER BY concreto."]
        return []
    sobran = list((Counter(ku) - Counter(ke)).elements())
    msgs = [f"El número de filas es correcto, pero {len(sobran)} de tus filas no coinciden con lo esperado."]
    if sobran:
        msgs.append(f"Por ejemplo, esta fila tuya no es correcta: {sobran[0]!r}.")
    return msgs


# --------------------------------------------------------------- correccion
_CACHE_REF: dict[tuple, Resultado] = {}


def corregir_sql(engine: Engine, sql_usuario: str, sql_referencia: str, *, ordenado: bool = False, alias: bool = False) -> dict:
    """Veredicto: estado (ok|fallo|error|error_banco), mensajes, error, columnas, filas, n_filas."""
    veredicto = {"estado": "ok", "mensajes": [], "error": "", "columnas": [], "filas": [], "n_filas": 0}

    problema, sql_u = validar_consulta(sql_usuario)
    if problema:
        veredicto.update(estado="error", error=problema)
        return veredicto

    try:
        res_u = ejecutar_consulta(engine, sql_u)
    except SQLAlchemyError as exc:
        veredicto.update(estado="error", error=_mensaje_error(exc))
        return veredicto

    veredicto.update(columnas=res_u.columnas, filas=[list(f) for f in res_u.filas[:20]], n_filas=len(res_u.filas))
    if res_u.truncado:
        veredicto.update(estado="fallo", mensajes=[f"Tu consulta devuelve más de {MAX_FILAS} filas. Revisa si falta un WHERE o si un JOIN multiplica filas."])
        return veredicto

    clave = (str(engine.url), sql_referencia)
    res_e = _CACHE_REF.get(clave)
    if res_e is None:
        try:
            res_e = ejecutar_consulta(engine, sql_referencia)
        except SQLAlchemyError as exc:
            veredicto.update(estado="error_banco", error=_mensaje_error(exc))
            return veredicto
        _CACHE_REF[clave] = res_e

    msgs = comparar_resultados(res_u, res_e, ordenado=ordenado, alias=alias)
    if msgs:
        veredicto.update(estado="fallo", mensajes=msgs)
    return veredicto
