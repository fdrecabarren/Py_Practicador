"""Piezas compartidas por las paginas de la app (cache, editor, textos)."""
from __future__ import annotations

import re

import streamlit as st

from motor import config, sesion, sql
from motor.banco import ErrorBanco, cargar_banco
from motor.progreso import Progreso


# --------------------------------------------------------------- recursos
@st.cache_resource(show_spinner=False)
def _banco_cacheado():
    return cargar_banco()


def get_banco():
    try:
        return _banco_cacheado()
    except ErrorBanco as exc:
        st.error("El banco de ejercicios tiene errores. Corrígelos y pulsa **Recargar banco** en Ajustes.")
        st.code("\n".join(exc.problemas), language="text")
        st.stop()


@st.cache_resource(show_spinner=False)
def get_progreso() -> Progreso:
    return Progreso()


@st.cache_resource(show_spinner=False)
def get_engine():
    """Engine de MySQL (solo lectura) o None si .env no tiene credenciales."""
    if sql.url_mysql() is None:
        return None
    return sql.crear_engine()


@st.cache_data(show_spinner=False, ttl=600)
def get_esquema() -> dict[str, list[str]]:
    engine = get_engine()
    return sql.listar_esquema(engine) if engine is not None else {}


def recargar_todo() -> None:
    _banco_cacheado.clear()
    get_engine.clear()
    get_esquema.clear()


# ------------------------------------------------------------------ editor
def _tema_editor() -> str:
    try:
        return "tomorrow_night" if st.context.theme.type == "dark" else "tomorrow"
    except Exception:  # noqa: BLE001 - versiones sin st.context.theme
        return "tomorrow"


def editor(valor: str, clave: str, *, lenguaje: str = "python", altura: int = 340) -> str:
    """Editor de codigo con tabulador y resaltado (streamlit-ace). Si no esta
    disponible, cae a un cuadro de texto normal."""
    try:
        from streamlit_ace import st_ace
    except ImportError:
        return st.text_area("Tu código", valor, key=clave, height=altura)
    texto = st_ace(
        value=valor, language=lenguaje, theme=_tema_editor(), keybinding="vscode",
        font_size=14, tab_size=4, wrap=True, show_gutter=True, auto_update=True,
        height=altura, key=clave,
    )
    return valor if texto is None else texto


# ----------------------------------------------------------------- textos
_CODIGO_MD = re.compile(r"(```.*?```|`[^`\n]*`)", re.S)
_DOLAR_ESCAPADO = "\\$"


def texto_md(texto: str) -> str:
    """Escapa el signo $ fuera de los bloques de codigo: Streamlit lo toma por una formula (LaTeX)
    y se comeria texto como $F$1 o $B11*H$11."""
    partes = _CODIGO_MD.split(texto)
    return "".join(p if i % 2 else p.replace("$", _DOLAR_ESCAPADO) for i, p in enumerate(partes))


ICONO_ESTADO = {
    "aprendido": (":green[:material/check_circle:]", "Aprendido"),
    "repetir": (":orange[:material/replay:]", "Para repetir"),
    "en_curso": (":blue[:material/edit:]", "En curso"),
    "nuevo": (":gray[:material/radio_button_unchecked:]", "Nuevo"),
    "bloqueado": (":gray[:material/lock:]", "Bloqueado"),
}


def estado_de(ej_id: str, prog: Progreso, aprendidos: set[str], bloqueado: bool) -> str:
    if ej_id in aprendidos:
        return "aprendido"
    if bloqueado:
        return "bloqueado"
    est = prog.estado_ejercicio(ej_id)
    if est is None:
        return "nuevo"
    return "repetir" if est["solucion_vista_dia"] else "en_curso"


def nombre_nivel(nivel: str) -> str:
    return config.NOMBRE_NIVEL.get(nivel, nivel)


def abrir_ejercicio(ej_id: str | None, tema: str | None = None) -> None:
    st.session_state["ejercicio_abierto"] = ej_id
    if tema:
        st.session_state["tema_actual"] = tema


# ------------------------------------------------------------- sesion de hoy
# La sesion en curso vive en la memoria de la app: {"items": [ItemSesion], "hechos": {ids resueltos}}.
def sesion_activa() -> dict | None:
    return st.session_state.get("sesion")


def iniciar_sesion(items: list) -> None:
    st.session_state["sesion"] = {"items": items, "hechos": set()}
    st.session_state.pop("sesion_resumen", None)


def abrir_primera_pendiente(banco) -> None:
    """Abre el primer ejercicio de la sesion sin resolver (o el ultimo si ya estan todos)."""
    s = sesion_activa()
    if not s:
        return
    pendiente = sesion.primer_pendiente(s["items"], s["hechos"]) or s["items"][-1].ejercicio_id
    abrir_ejercicio(pendiente, banco.ejercicios[pendiente].tema)


def terminar_sesion() -> None:
    """Cierra la sesion y deja guardado su resumen para mostrarlo en Practicar."""
    s = st.session_state.pop("sesion", None)
    if s:
        st.session_state["sesion_resumen"] = sesion.resumen(s["items"], s["hechos"])
    st.session_state["ejercicio_abierto"] = None
