"""Pantalla de practica: lista de ejercicios por tema/nivel y vista de un ejercicio."""
import pandas as pd
import streamlit as st

from motor import niveles, sql
from motor.ejecutor_python import ejecutar_python
from paginas import comun

banco = comun.get_banco()
prog = comun.get_progreso()

LENGUAJE = {"python": "python", "sql": "sql", "test": "text"}
ETIQUETA_PISTA = {0: "idea general", 1: "pista concreta"}


# =============================================================== utilidades
def _cerrar() -> None:
    st.session_state["ejercicio_abierto"] = None


def _pedir_pista(clave: str, n: int) -> None:
    st.session_state[clave] = n


def _reiniciar_codigo(ej) -> None:
    st.session_state[f"codigo:{ej.id}"] = ej.codigo_inicial
    st.session_state[f"reinicio:{ej.id}"] = st.session_state.get(f"reinicio:{ej.id}", 0) + 1
    st.session_state.pop(f"res:{ej.id}", None)


def _niveles_superados(tema: str) -> dict[str, bool]:
    return {e.nivel: e.superado for e in niveles.estado_niveles(banco, tema, prog.aprendidos())}


def _registrar(ej, correcto: bool) -> dict:
    """Guarda el intento y avisa si se acaba de superar un nivel."""
    antes = _niveles_superados(ej.tema)
    pista_max = st.session_state.get(f"pistas:{ej.id}", 0) + (1 if st.session_state.get(f"sol:{ej.id}") else 0)
    resultado = prog.registrar_intento(ej, correcto, pista_max)
    despues = _niveles_superados(ej.tema)
    for nivel, ok in despues.items():
        if ok and not antes.get(nivel):
            st.toast(f"Has superado el nivel {comun.nombre_nivel(nivel)} de {banco.temas[ej.tema].nombre}", icon=":material/emoji_events:")
    return resultado


def _siguiente(ej):
    if ej.tipo == "test":
        pendientes = [e for e in sorted(banco.por_tema(ej.tema), key=lambda x: x.id)
                      if e.tipo == "test" and e.id != ej.id and e.id not in prog.aprendidos()]
        return pendientes[0] if pendientes else None
    return niveles.siguiente_ejercicio(banco, ej.tema, prog.aprendidos(), excluir=ej.id)


# ================================================================ lista
def vista_lista() -> None:
    st.title("Practicar")
    temas = banco.temas_ordenados()
    ids = [t.id for t in temas]
    actual = st.session_state.get("tema_actual")
    tema_id = st.radio(
        "Tema", ids, index=ids.index(actual) if actual in ids else 0,
        format_func=lambda i: banco.temas[i].nombre, horizontal=True,
    )
    st.session_state["tema_actual"] = tema_id
    tema = banco.temas[tema_id]
    st.caption(tema.descripcion)

    aprendidos = prog.aprendidos()
    estados = niveles.estado_niveles(banco, tema_id, aprendidos)
    nivel_ahora = niveles.nivel_actual(estados)

    sig = niveles.siguiente_ejercicio(banco, tema_id, aprendidos)
    if sig:
        st.button(f"Continuar: {sig.titulo}", type="primary", icon=":material/play_arrow:",
                  on_click=comun.abrir_ejercicio, args=(sig.id, tema_id))

    for e in estados:
        if e.total == 0:
            continue
        resumen = f"{comun.nombre_nivel(e.nivel)}: {e.aprendidos}/{e.total} aprendidos"
        resumen += " (superado)" if e.superado else (" (bloqueado)" if e.bloqueado else f" (necesitas {e.necesarios})")
        with st.expander(resumen, expanded=(e.nivel == nivel_ahora)):
            if e.bloqueado:
                st.info("Se desbloquea al superar el nivel anterior con un 70 % o más de ejercicios aprendidos.", icon=":material/lock:")
            for ej in sorted(banco.por_tema_y_nivel(tema_id, e.nivel), key=lambda x: x.id):
                estado = comun.estado_de(ej.id, prog, aprendidos, e.bloqueado)
                icono, texto = comun.ICONO_ESTADO[estado]
                c1, c2, c3 = st.columns([0.5, 5, 1.3], vertical_alignment="center")
                c1.markdown(icono, help=texto)
                c2.markdown(f"**{ej.titulo}**  \n:gray[{ej.concepto} · {texto}]")
                c3.button("Abrir", key=f"abrir_{ej.id}", disabled=e.bloqueado,
                          on_click=comun.abrir_ejercicio, args=(ej.id, tema_id))

    preguntas = sorted([x for x in banco.por_tema(tema_id) if x.tipo == "test"], key=lambda x: x.id)
    if preguntas:
        hechas = sum(1 for q in preguntas if q.id in aprendidos)
        with st.expander(f"Preguntas rápidas para calentar: {hechas}/{len(preguntas)} acertadas"):
            for q in preguntas:
                icono, texto = comun.ICONO_ESTADO["aprendido" if q.id in aprendidos else "nuevo"]
                c1, c2, c3 = st.columns([0.5, 5, 1.3], vertical_alignment="center")
                c1.markdown(icono, help=texto)
                c2.markdown(f"**{q.titulo}**  \n:gray[{q.concepto}]")
                c3.button("Responder", key=f"abrir_{q.id}", on_click=comun.abrir_ejercicio, args=(q.id, tema_id))


# ========================================================= vista de ejercicio
@st.dialog("Ver la solución")
def dialogo_solucion(ej) -> None:
    st.write(
        "Si ves la solución, este ejercicio contará como **no aprendido** y volverá más adelante. "
        "Resolverlo hoy mismo después de verla no cuenta: tendrás que repetirlo otro día."
    )
    c1, c2 = st.columns(2)
    if c1.button("Sí, mostrar la solución", type="primary"):
        prog.registrar_solucion_vista(ej)
        st.session_state[f"sol:{ej.id}"] = True
        st.rerun()
    if c2.button("Cancelar"):
        st.rerun()


def bloque_pistas(ej) -> None:
    pk, sk = f"pistas:{ej.id}", f"sol:{ej.id}"
    nivel_p = st.session_state.get(pk, 0)
    st.markdown("##### Ayuda")
    for i in range(nivel_p):
        st.info(f"**Pista {i + 1} ({ETIQUETA_PISTA[i]}).** {ej.pistas[i]}", icon=":material/lightbulb:")
    if nivel_p < 2:
        st.button(f"Pedir pista {nivel_p + 1} ({ETIQUETA_PISTA[nivel_p]})", key=f"btn_pista_{ej.id}",
                  on_click=_pedir_pista, args=(pk, nivel_p + 1), icon=":material/lightbulb:")

    if st.session_state.get(sk):
        st.warning("Has visto la solución: este ejercicio cuenta como no aprendido y volverá más adelante.", icon=":material/visibility:")
        st.markdown(f"**Solución explicada.** {ej.pistas[2]}")
        st.code(ej.solucion, language=LENGUAJE[ej.tipo])
        return

    puede = prog.puede_ver_solucion(ej.id)
    ya_vista = (prog.estado_ejercicio(ej.id) or {}).get("solucion_vista_dia")
    if st.button("Ver solución explicada", key=f"btn_sol_{ej.id}", disabled=not puede, icon=":material/visibility:",
                 help=None if puede else "Se desbloquea después de tu primer intento (botón Comprobar)."):
        if ya_vista:
            st.session_state[sk] = True
            st.rerun()
        else:
            dialogo_solucion(ej)
    if not puede:
        st.caption("La solución se desbloquea después de tu primer intento con **Comprobar**.")


# ------------------------------------------------------- resultados (python)
def mostrar_resultado_python(res: dict, ej) -> None:
    r, modo = res["r"], res["modo"]
    if r.get("stdout"):
        st.markdown("**Salida de tu programa**")
        st.code(r["stdout"], language="text")
    estado = r["estado"]
    if estado == "ok" and modo == "ejecutar":
        st.success("Tu código se ha ejecutado sin errores.")
        if r.get("vista"):
            st.markdown("**Lo que vale `resultado`**")
            st.code(r["vista"], language="text")
    elif estado == "ok":
        st.success("Correcto. Has pasado todos los tests.", icon=":material/check_circle:")
        if res.get("aviso"):
            st.warning(res["aviso"])
    elif estado == "fallo":
        st.error("Todavía no. Tu código se ejecuta, pero el resultado no es el esperado.", icon=":material/close:")
        for m in r["mensajes"]:
            st.markdown(f"- {m}")
        if r.get("vista"):
            with st.expander("Lo que ha devuelto tu código", expanded=True):
                st.code(r["vista"], language="text")
    elif estado == "error":
        st.error("Tu código ha producido un error de Python:", icon=":material/error:")
        st.code(r["traceback"], language="pytb")
        st.caption("Cómo leerlo: empieza por la **última línea** (tipo de error y motivo) y busca después "
                   "`File \"<tu_codigo>\", line N`, que indica en qué línea de tu código ocurrió.")
        for m in r.get("mensajes", []):
            st.markdown(f"- {m}")
    elif estado == "timeout":
        st.error(r["mensajes"][0], icon=":material/timer_off:")
    elif estado == "sin_datos":
        st.warning(r["mensajes"][0])
    elif estado == "error_banco":
        st.error("Este ejercicio tiene un fallo interno (no es culpa tuya). Avísame para corregirlo.")
        st.code(r["traceback"], language="pytb")


def accion_python(ej, codigo: str, accion: str) -> None:
    rk = f"res:{ej.id}"
    if accion == "ejecutar":
        entrada = next((t.get("entrada", "") for t in ej.tests if t.get("tipo") == "salida"), "")
        with st.spinner("Ejecutando..."):
            r = ejecutar_python(codigo, datos=ej.datos, modo="ejecutar", entrada=entrada, timeout=ej.timeout)
        st.session_state[rk] = {"modo": "ejecutar", "r": r}
    else:
        with st.spinner("Comprobando..."):
            r = ejecutar_python(codigo, solucion=ej.solucion, tests=ej.tests, comparar=ej.comparar,
                                datos=ej.datos, timeout=ej.timeout)
        aviso = None
        if r["estado"] in ("ok", "fallo", "error", "timeout"):
            aviso = _registrar(ej, r["estado"] == "ok")["aviso"]
        st.session_state[rk] = {"modo": "comprobar", "r": r, "aviso": aviso}


# ----------------------------------------------------------- resultados (sql)
def mostrar_resultado_sql(res: dict, ej) -> None:
    v, modo = res["v"], res["modo"]
    estado = v["estado"]
    if estado == "error":
        st.error("MySQL (o el validador) ha devuelto un error:", icon=":material/error:")
        st.code(v["error"], language="text")
        return
    if estado == "error_banco":
        st.error("Este ejercicio tiene un fallo interno (no es culpa tuya). Avísame para corregirlo.")
        st.code(v["error"], language="text")
        return
    if modo == "comprobar":
        if estado == "ok":
            st.success("Correcto. Tu consulta devuelve lo mismo que la de referencia.", icon=":material/check_circle:")
            if res.get("aviso"):
                st.warning(res["aviso"])
        else:
            st.error("Todavía no. Tu consulta se ejecuta, pero el resultado no es el esperado.", icon=":material/close:")
            for m in v["mensajes"]:
                st.markdown(f"- {m}")
    else:
        st.success(f"Consulta ejecutada: {v['n_filas']} fila(s).")
    if v["columnas"]:
        st.caption(f"Tu resultado ({v['n_filas']} fila(s); se muestran las 20 primeras):")
        st.dataframe(pd.DataFrame(v["filas"], columns=v["columnas"]), hide_index=True, use_container_width=True)


def accion_sql(ej, consulta: str, accion: str, engine) -> None:
    rk = f"res:{ej.id}"
    if accion == "ejecutar":
        problema, limpio = sql.validar_consulta(consulta)
        if problema:
            v = {"estado": "error", "error": problema, "columnas": [], "filas": [], "n_filas": 0, "mensajes": []}
        else:
            try:
                r = sql.ejecutar_consulta(engine, limpio)
                v = {"estado": "ok", "error": "", "mensajes": [], "columnas": r.columnas,
                     "filas": [list(f) for f in r.filas[:20]], "n_filas": len(r.filas)}
            except Exception as exc:  # noqa: BLE001 - se enseña el error real
                v = {"estado": "error", "error": sql._mensaje_error(exc), "columnas": [], "filas": [], "n_filas": 0, "mensajes": []}
        st.session_state[rk] = {"modo": "ejecutar", "v": v}
    else:
        with st.spinner("Comprobando..."):
            v = sql.corregir_sql(engine, consulta, ej.solucion,
                                 ordenado=bool(ej.comparar.get("ordenado")), alias=bool(ej.comparar.get("alias")))
        aviso = None
        if v["estado"] in ("ok", "fallo", "error"):
            aviso = _registrar(ej, v["estado"] == "ok")["aviso"]
        st.session_state[rk] = {"modo": "comprobar", "v": v, "aviso": aviso}


# ---------------------------------------------------------------- pregunta test
def vista_pregunta(ej) -> None:
    rk = f"res:{ej.id}"
    res = st.session_state.get(rk)
    elegida = st.radio("Elige una respuesta", range(len(ej.opciones)), format_func=lambda i: ej.opciones[i],
                       index=None, key=f"op:{ej.id}", disabled=res is not None)
    if res is None:
        if st.button("Responder", type="primary", disabled=elegida is None):
            correcto = elegida == ej.correcta
            aviso = _registrar(ej, correcto)["aviso"]
            st.session_state[rk] = {"correcto": correcto, "elegida": elegida, "aviso": aviso}
            st.rerun()
        return
    if res["correcto"]:
        st.success("Correcto.", icon=":material/check_circle:")
    else:
        st.error(f"No es esa. La respuesta correcta es: **{ej.opciones[ej.correcta]}**", icon=":material/close:")
    st.markdown(ej.explicacion)
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Intentar otra vez"):
        st.session_state.pop(rk, None)
        st.session_state.pop(f"op:{ej.id}", None)
        st.rerun()
    sig = _siguiente(ej)
    if sig:
        c2.button("Siguiente pregunta", type="primary", on_click=comun.abrir_ejercicio, args=(sig.id, ej.tema))


# ------------------------------------------------------------ vista principal
def vista_ejercicio(ej) -> None:
    st.button("Volver a la lista", on_click=_cerrar, icon=":material/arrow_back:")
    st.title(ej.titulo if ej.tipo != "test" else f"Pregunta rápida: {ej.titulo}")
    estado_db = prog.estado_ejercicio(ej.id)
    marca = ""
    if ej.id in prog.aprendidos():
        marca = " · :green[aprendido]"
    elif estado_db and estado_db["solucion_vista_dia"]:
        marca = " · :orange[para repetir (viste la solución)]"
    st.caption(f"{banco.temas[ej.tema].nombre} · {ej.concepto} · nivel {comun.nombre_nivel(ej.nivel)}{marca}")
    st.caption(f"Sale de: {ej.origen}")

    if ej.tipo == "test":
        st.markdown(ej.enunciado)
        vista_pregunta(ej)
        return

    izq, der = st.columns([1, 1.15], gap="large")
    # Se rellena primero la columna derecha (editor y botones) para que la ayuda de la izquierda
    # ya vea el intento recien registrado (por ejemplo, para desbloquear la solucion).
    with der:
        engine = None
        if ej.tipo == "sql":
            engine = comun.get_engine()
            if engine is None:
                st.warning("Falta configurar la conexión a MySQL (archivo `.env`). Mira la página **Conexión y ajustes**.",
                           icon=":material/database_off:")
            else:
                with st.expander("Tablas y columnas de Olist"):
                    for tabla, cols in comun.get_esquema().items():
                        st.markdown(f"**{tabla}**: " + ", ".join(f"`{c}`" for c in cols))

        ek = f"codigo:{ej.id}"
        st.session_state.setdefault(ek, ej.codigo_inicial)
        contador = st.session_state.get(f"reinicio:{ej.id}", 0)
        codigo = comun.editor(st.session_state[ek], f"ace:{ej.id}:{contador}", lenguaje=LENGUAJE[ej.tipo])
        st.session_state[ek] = codigo

        deshabilitar = ej.tipo == "sql" and engine is None
        b1, b2, b3 = st.columns([1.2, 1.4, 0.6])
        ejecutar = b1.button("Ejecutar", disabled=deshabilitar, icon=":material/play_arrow:",
                             help="Prueba tu código sin que cuente como intento.", use_container_width=True)
        comprobar = b2.button("Comprobar", type="primary", disabled=deshabilitar, icon=":material/task_alt:",
                              help="Corrige tu solución. Cuenta como intento.", use_container_width=True)
        b3.button("", on_click=_reiniciar_codigo, args=(ej,), icon=":material/restart_alt:",
                  help="Restablecer el código inicial", use_container_width=True)

        accion = "comprobar" if comprobar else ("ejecutar" if ejecutar else None)
        if accion:
            if ej.tipo == "python":
                accion_python(ej, codigo, accion)
            else:
                accion_sql(ej, codigo, accion, engine)

        res = st.session_state.get(f"res:{ej.id}")
        if res:
            if ej.tipo == "python":
                mostrar_resultado_python(res, ej)
                correcto = res["modo"] == "comprobar" and res["r"]["estado"] == "ok"
            else:
                mostrar_resultado_sql(res, ej)
                correcto = res["modo"] == "comprobar" and res["v"]["estado"] == "ok"
            if correcto:
                with st.expander("Por qué funciona", expanded=True):
                    st.markdown(ej.explicacion)
                sig = _siguiente(ej)
                if sig:
                    st.button(f"Siguiente: {sig.titulo}", type="primary", on_click=comun.abrir_ejercicio, args=(sig.id, ej.tema),
                              icon=":material/arrow_forward:")

    with izq:
        st.markdown(ej.enunciado)
        if ej.nota_dialecto:
            st.caption(f"Nota de dialecto: {ej.nota_dialecto}")
        if ej.datos:
            st.caption("Archivos disponibles en la carpeta de trabajo: " + ", ".join(f"`{d}`" for d in ej.datos))
        bloque_pistas(ej)


# ==================================================================== main
abierto = st.session_state.get("ejercicio_abierto")
if abierto and abierto in banco.ejercicios:
    ej_abierto = banco.ejercicios[abierto]
    if niveles.esta_bloqueado(banco, abierto, prog.aprendidos()):
        st.warning("Este ejercicio está bloqueado: supera antes el nivel anterior.")
        st.session_state["ejercicio_abierto"] = None
        vista_lista()
    else:
        vista_ejercicio(ej_abierto)
else:
    vista_lista()
