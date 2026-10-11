import streamlit as st

from motor import niveles, sesion
from paginas import comun

banco = comun.get_banco()
prog = comun.get_progreso()
aprendidos = prog.aprendidos()

st.title("Practicador")
st.caption("Practica lo que vas viendo en el bootcamp con tus propios datos de Kiva y Olist. Intenta primero, pide pistas después.")

racha = prog.racha()
ids_con_nivel = {e.id for e in banco.ejercicios.values() if e.cuenta_nivel}
c1, c2, c3, c4 = st.columns(4)
c1.metric("Racha actual", f"{racha['actual']} día(s)")
c2.metric("Mejor racha", f"{racha['mejor']} día(s)")
c3.metric("Ejercicios aprendidos", f"{len(aprendidos & ids_con_nivel)} / {len(ids_con_nivel)}")
c4.metric("Intentos hoy", prog.intentos_de_hoy())

vencidos = [r for r in prog.repasos_vencidos() if r["ejercicio_id"] in banco.ejercicios]
if vencidos:
    st.warning(f"Hoy toca repasar {len(vencidos)} ejercicio(s). Los encuentras en la sesión de hoy y en Mi progreso.",
               icon=":material/replay:")
if not racha["hoy_practicado"]:
    st.info("Hoy todavía no has practicado. Con un solo ejercicio mantienes la racha.", icon=":material/local_fire_department:")

# --- Seguir donde lo dejé
temas = banco.temas_ordenados()
ultimo = prog.ultimo_tema()
orden_temas = ([t for t in temas if t.id == ultimo] + [t for t in temas if t.id != ultimo]) if ultimo else temas
siguiente = None
for t in orden_temas:
    siguiente = niveles.siguiente_ejercicio(banco, t.id, aprendidos)
    if siguiente:
        break

izq, der = st.columns([2, 1])
with izq:
    if siguiente:
        st.subheader("Siguiente ejercicio recomendado")
        st.markdown(
            f"**{siguiente.titulo}**  \n{banco.temas[siguiente.tema].nombre} · {siguiente.concepto} · "
            f"nivel {comun.nombre_nivel(siguiente.nivel)}"
        )
        if st.button("Empezar", type="primary", icon=":material/play_arrow:"):
            comun.abrir_ejercicio(siguiente.id, siguiente.tema)
            st.switch_page("paginas/practicar.py")
    else:
        st.success("Has aprendido todos los ejercicios disponibles. Pide más al ampliar el banco.", icon=":material/emoji_events:")
with der:
    st.subheader("Sesión de hoy")
    en_curso = comun.sesion_activa()
    if en_curso:
        total = len(en_curso["items"])
        hechos = len(en_curso["hechos"] & {i.ejercicio_id for i in en_curso["items"]})
        st.caption(f"Sesión en curso: {hechos} de {total} resueltos.")
        if st.button("Continuar sesión", type="primary", icon=":material/play_arrow:"):
            comun.abrir_primera_pendiente(banco)
            st.switch_page("paginas/practicar.py")
    else:
        previa = sesion.armar_sesion(banco, prog)
        if previa:
            n_rep = sum(1 for i in previa if i.motivo == "repaso")
            partes = []
            if n_rep:
                partes.append(f"{n_rep} repaso(s)")
            if len(previa) - n_rep:
                partes.append(f"{len(previa) - n_rep} nuevo(s)")
            st.caption(f"Hoy: {' y '.join(partes)}, unos {sesion.minutos_totales(banco, previa)} minutos.")
            if st.button("Empezar sesión de 20 minutos", type="primary", icon=":material/timer:"):
                comun.iniciar_sesion(previa)
                comun.abrir_primera_pendiente(banco)
                st.switch_page("paginas/practicar.py")
        else:
            st.button("Empezar sesión de 20 minutos", disabled=True)
            st.caption("No hay nada pendiente: lo has aprendido todo y no tienes repasos.")
    st.caption("Mezcla repasos de lo que fallaste (a 1, 3 y 7 días) con 1 o 2 ejercicios nuevos de tu nivel.")

# --- Estado por tema
st.divider()
st.subheader("Tus temas")
POR_FILA = 3
cols = [c for i in range(0, len(temas), POR_FILA) for c in st.columns(POR_FILA)][:len(temas)]
for col, tema in zip(cols, temas):
    estados = niveles.estado_niveles(banco, tema.id, aprendidos)
    actual = niveles.nivel_actual(estados)
    with col, st.container(border=True):
        st.markdown(f"**{tema.nombre}**")
        st.caption(tema.descripcion)
        st.markdown(f"Nivel actual: **{comun.nombre_nivel(actual)}**")
        for e in estados:
            if e.total == 0:
                continue
            etiqueta = f"{comun.nombre_nivel(e.nivel)}: {e.aprendidos}/{e.total}"
            if e.superado:
                etiqueta += " (superado)"
            elif e.bloqueado:
                etiqueta += " (bloqueado)"
            else:
                etiqueta += f" (necesitas {e.necesarios})"
            st.progress(e.porcentaje, text=etiqueta)
        if st.button("Practicar", key=f"ir_{tema.id}"):
            st.session_state["tema_actual"] = tema.id
            st.session_state["ejercicio_abierto"] = None
            st.switch_page("paginas/practicar.py")
