from datetime import timedelta

import pandas as pd
import streamlit as st

from motor import niveles
from paginas import comun

banco = comun.get_banco()
prog = comun.get_progreso()
aprendidos = prog.aprendidos()

st.title("Mi progreso")

racha = prog.racha()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Racha actual", f"{racha['actual']} día(s)")
c2.metric("Mejor racha", f"{racha['mejor']} día(s)")
c3.metric("Días practicados", racha["total"])
c4.metric("Intentos hoy", prog.intentos_de_hoy())

# --- últimos 14 días
dias = set(prog.dias_practicados())
hoy = prog.hoy()
ultimos = [hoy - timedelta(days=i) for i in range(13, -1, -1)]
st.caption("Últimos 14 días")
cols = st.columns(14)
for col, d in zip(cols, ultimos):
    col.markdown(
        (":green[:material/check_circle:]" if d in dias else ":gray[:material/radio_button_unchecked:]") + f"  \n{d.day}/{d.month}"
    )

# --- niveles por tema
st.subheader("Niveles por tema")
filas = []
for tema in banco.temas_ordenados():
    for e in niveles.estado_niveles(banco, tema.id, aprendidos):
        if e.total == 0:
            continue
        estado = "Superado" if e.superado else ("Bloqueado" if e.bloqueado else "En curso")
        filas.append({
            "Tema": tema.nombre, "Nivel": comun.nombre_nivel(e.nivel),
            "Aprendidos": e.aprendidos, "Total": e.total, "Necesarios (70 %)": e.necesarios, "Estado": estado,
        })
st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)

# --- por concepto
st.subheader("Aciertos por concepto")
stats = prog.stats_por_concepto()
if stats:
    df = pd.DataFrame(stats)
    df["Tema"] = df["tema"].map(lambda t: banco.temas[t].nombre if t in banco.temas else t)
    df["% acierto"] = (df["aciertos"] / df["intentos"] * 100).round(0).astype(int)
    df = df.rename(columns={"concepto": "Concepto", "intentos": "Intentos", "aciertos": "Aciertos", "aprendidos": "Ejercicios aprendidos"})
    st.dataframe(df[["Tema", "Concepto", "Intentos", "Aciertos", "% acierto", "Ejercicios aprendidos"]]
                 .sort_values(["% acierto", "Intentos"]), hide_index=True, use_container_width=True)
else:
    st.info("Todavía no hay intentos. Resuelve un ejercicio y aparecerá aquí.")

# --- para repetir
st.subheader("Para repetir")
repetir = [i for i in prog.no_aprendidos() if i in banco.ejercicios]
if repetir:
    st.caption("Ejercicios cuya solución viste. Vuelve a resolverlos en un día distinto, sin mirarla, para que cuenten.")
    for ej_id in repetir:
        ej = banco.ejercicios[ej_id]
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        c1.markdown(f"**{ej.titulo}**  \n:gray[{banco.temas[ej.tema].nombre} · {ej.concepto}]")
        if c2.button("Abrir", key=f"rep_{ej_id}"):
            comun.abrir_ejercicio(ej_id, ej.tema)
            st.switch_page("paginas/practicar.py")
else:
    st.success("No tienes ejercicios pendientes de repetir.")

# --- reinicio
with st.expander("Borrar todo mi progreso"):
    st.warning("Esto elimina intentos, ejercicios aprendidos y racha. No se puede deshacer.")
    if st.checkbox("Entiendo que se borrará todo"):
        if st.button("Borrar progreso", type="primary"):
            prog.reiniciar()
            st.success("Progreso borrado.")
            st.rerun()
