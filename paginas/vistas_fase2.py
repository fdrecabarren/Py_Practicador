"""Paneles de los ejercicios de Excel y de Terminal/Git (fase 2).

Se usan desde paginas/practicar.py: reciben las funciones de esa pagina que registran
el intento (`registrar`) y que dan el siguiente ejercicio (`siguiente`).
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from motor import config, excel, terminal
from paginas import comun

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ================================================================ piezas comunes
def mostrar_comprobaciones(comprobaciones: list[dict]) -> None:
    """Lista de comprobaciones con su estado. Las de fallo explican que mirar, sin dar la respuesta."""
    for c in comprobaciones:
        if c["ok"]:
            st.markdown(f":green[:material/check_circle:] {comun.texto_md(c['titulo'])}")
        elif c["blando"]:
            st.markdown(f":orange[:material/info:] {comun.texto_md(c['titulo'])}  \n&nbsp;&nbsp;&nbsp;&nbsp;:gray[{comun.texto_md(c['mensaje'])}]")
        else:
            st.markdown(f":red[:material/close:] {comun.texto_md(c['titulo'])}  \n&nbsp;&nbsp;&nbsp;&nbsp;:gray[{comun.texto_md(c['mensaje'])}]")


def _veredicto(res: dict, ej, siguiente) -> None:
    """Banner de resultado y, si es correcto, la explicacion y el boton de seguir."""
    r, modo = res["r"], res["modo"]
    estado = r["estado"]
    if estado == "ok":
        if modo == "comprobar":
            st.success("Correcto. Has pasado todas las comprobaciones.", icon=":material/check_circle:")
            if res.get("aviso"):
                st.warning(res["aviso"])
        else:
            st.success("Todo bien por ahora (esta revisión no cuenta como intento).", icon=":material/check_circle:")
    elif estado == "fallo":
        st.error("Todavía no. Esto es lo que falta:", icon=":material/close:")
    elif estado == "archivo_invalido":
        st.error(r["mensajes"][0], icon=":material/error:")
    elif estado == "sin_preparar":
        st.warning(r["mensajes"][0])
    elif estado == "error_banco":
        st.error("Este ejercicio tiene un fallo interno (no es culpa tuya). Avísame para corregirlo.")
        st.code("\n".join(r["mensajes"]), language="text")
    elif estado == "error":
        st.error(r["mensajes"][0])
    if r.get("comprobaciones"):
        mostrar_comprobaciones(r["comprobaciones"])
    if estado == "ok" and modo == "comprobar":
        with st.expander("Por qué funciona", expanded=True):
            st.markdown(comun.texto_md(ej.explicacion))
        sig = siguiente(ej)
        if sig:
            st.button(f"Siguiente: {sig.titulo}", type="primary", on_click=comun.abrir_ejercicio, args=(sig.id, ej.tema),
                      icon=":material/arrow_forward:")


# ====================================================================== Excel
def panel_excel(ej, registrar, siguiente) -> None:
    rk = f"res:{ej.id}"
    st.markdown("##### Tu archivo")
    st.caption(
        "Descarga el libro, resuélvelo en **Excel de escritorio** (no la vista previa), guárdalo con **Ctrl+G** y súbelo aquí. "
        "Las fórmulas se guardan en inglés dentro del archivo, así que da igual que tu Excel esté en español."
    )
    try:
        datos = excel.generar_libro(ej)
    except excel.ErrorExcel as exc:
        st.warning(f"{exc}", icon=":material/folder_off:")
        return
    st.download_button("Descargar el archivo de práctica", datos, file_name=ej.nombre_archivo, mime=XLSX,
                       icon=":material/download:", key=f"dl:{ej.id}", on_click="ignore")
    archivo = st.file_uploader("Sube tu archivo resuelto (.xlsx)", type=["xlsx"], key=f"up:{ej.id}")

    b1, b2 = st.columns(2)
    revisar = b1.button("Revisar sin contar", disabled=archivo is None, icon=":material/fact_check:",
                        help="Comprueba tu archivo sin que cuente como intento.", use_container_width=True)
    comprobar = b2.button("Comprobar", type="primary", disabled=archivo is None, icon=":material/task_alt:",
                          help="Corrige tu solución. Cuenta como intento.", use_container_width=True)
    if revisar or comprobar:
        with st.spinner("Leyendo tu archivo..."):
            r = excel.corregir_excel(ej, archivo.getvalue())
        aviso = None
        if comprobar and r["estado"] in ("ok", "fallo"):
            aviso = registrar(ej, r["estado"] == "ok")["aviso"]
        st.session_state[rk] = {"modo": "comprobar" if comprobar else "revisar", "r": r, "aviso": aviso}
    if archivo is None and not st.session_state.get(rk):
        st.caption("Cuando tengas el archivo resuelto, súbelo para revisarlo.")
    res = st.session_state.get(rk)
    if res:
        _veredicto(res, ej, siguiente)


# =================================================================== Terminal
def _ruta_bash(ruta: Path) -> str:
    """Ruta al estilo Git Bash: E:\\a\\b -> /e/a/b."""
    p = ruta.resolve()
    if p.drive:
        return "/" + p.drive.rstrip(":").lower() + p.as_posix()[len(p.drive):]
    return p.as_posix()


def panel_terminal(ej, registrar, siguiente) -> None:
    rk = f"res:{ej.id}"
    if terminal.encontrar_bash() is None or terminal.encontrar_git() is None:
        st.error("Para estos ejercicios hace falta **Git for Windows** (incluye Git Bash). "
                 "Instálalo desde https://git-scm.com/downloads y reinicia la app.", icon=":material/terminal:")
        return
    preparado = terminal.esta_preparado(ej.id)
    trabajo = terminal.dir_trabajo(ej.id)

    st.markdown("##### Tu carpeta de práctica")
    st.caption("Es una carpeta propia de este ejercicio, dentro de la app: no toca ninguno de tus repositorios reales.")

    if not preparado:
        if st.button("Preparar ejercicio", type="primary", icon=":material/folder_open:", key=f"prep:{ej.id}"):
            _preparar(ej)
            st.rerun()
        st.caption("Pulsa para crear la carpeta con el punto de partida del enunciado.")
        res = st.session_state.get(rk)
        if res:
            _veredicto(res, ej, siguiente)
        return

    st.code(_ruta_bash(trabajo), language="bash")
    c1, c2, c3 = st.columns([1.4, 1.3, 1.0])
    if c1.button("Abrir Git Bash aquí", icon=":material/terminal:", key=f"bash:{ej.id}", use_container_width=True,
                 help="Abre Git Bash dentro de la carpeta del ejercicio."):
        ok, msg = terminal.abrir_git_bash(ej.id)
        st.toast("Git Bash abierto." if ok else msg, icon=":material/terminal:" if ok else ":material/error:")
    ver = c2.button("Ver estado", icon=":material/visibility:", key=f"btn_estado:{ej.id}", use_container_width=True,
                    help="Muestra los archivos, git status y el historial. Solo lee: no cuenta como intento.")
    with c3.popover("Reiniciar", icon=":material/restart_alt:", use_container_width=True):
        st.write("Se borra lo que hayas hecho en esta carpeta y vuelve al punto de partida.")
        if st.button("Sí, reiniciar", key=f"reset:{ej.id}", type="primary"):
            _preparar(ej)
            st.rerun()
    with st.expander("¿Prefieres tu propia terminal?"):
        st.markdown("Entra con `cd` en la carpeta de arriba y, **antes de usar git**, ejecuta esta línea. "
                    "Evita que git vea el repositorio del propio proyecto mientras no hayas hecho `git init`:")
        st.code(f'export GIT_CEILING_DIRECTORIES="{_ruta_bash(config.RAIZ)}"', language="bash")
        st.caption("El botón de Git Bash ya lo hace por ti.")

    comprobar = st.button("Comprobar", type="primary", icon=":material/task_alt:", key=f"comp:{ej.id}",
                          help="Corrige el estado de la carpeta. Cuenta como intento.")
    if ver:
        try:
            st.session_state[f"vista_estado:{ej.id}"] = terminal.estado_repo(ej)
        except terminal.ErrorTerminal as exc:
            st.session_state[f"vista_estado:{ej.id}"] = str(exc)
    if comprobar:
        with st.spinner("Comprobando..."):
            r = terminal.comprobar(ej)
        aviso = None
        if r["estado"] in ("ok", "fallo"):
            aviso = registrar(ej, r["estado"] == "ok")["aviso"]
        st.session_state[rk] = {"modo": "comprobar", "r": r, "aviso": aviso}

    if st.session_state.get(f"vista_estado:{ej.id}"):
        with st.expander("Estado de la carpeta (solo lectura)", expanded=True):
            st.code(st.session_state[f"vista_estado:{ej.id}"], language="text")
    res = st.session_state.get(rk)
    if res:
        _veredicto(res, ej, siguiente)


def _preparar(ej) -> None:
    """Crea (o reinicia) la carpeta de trabajo y limpia los resultados anteriores del ejercicio."""
    st.session_state.pop(f"res:{ej.id}", None)
    st.session_state.pop(f"vista_estado:{ej.id}", None)
    try:
        r = terminal.preparar(ej)
    except terminal.ErrorTerminal as exc:
        st.session_state[f"res:{ej.id}"] = {"modo": "revisar", "r": {"estado": "error", "mensajes": [str(exc)], "comprobaciones": []}}
        return
    if not r["ok"]:
        st.session_state[f"res:{ej.id}"] = {"modo": "revisar", "r": {"estado": "error", "mensajes": [r["error"]], "comprobaciones": []}}
