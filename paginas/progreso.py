from datetime import timedelta

import pandas as pd
import streamlit as st

from motor import niveles, repaso
from paginas import comun

banco = comun.get_banco()
prog = comun.get_progreso()
aprendidos = prog.aprendidos()

st.title("Mi progreso")

racha = prog.racha()
programados = [r for r in prog.repasos_programados() if r["ejercicio_id"] in banco.ejercicios]
hoy = prog.hoy()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Racha actual", f"{racha['actual']} día(s)")
c2.metric("Mejor racha", f"{racha['mejor']} día(s)")
c3.metric("Días practicados", racha["total"])
c4.metric("Intentos hoy", prog.intentos_de_hoy())
c5.metric("Repasos que tocan hoy", sum(1 for r in programados if r["proxima"] <= hoy))

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

# --- intentos de los ultimos 30 dias
st.subheader("Últimos 30 días")
serie = prog.intentos_por_dia(30)
if any(s["intentos"] for s in serie):
    grafico = pd.DataFrame({
        "Día": [s["dia"] for s in serie],
        "Aciertos": [s["aciertos"] for s in serie],
        "Fallos": [s["intentos"] - s["aciertos"] for s in serie],
    }).set_index("Día")
    st.bar_chart(grafico, color=["#22c55e", "#ef4444"])
else:
    st.caption("Todavía no hay intentos en los últimos 30 días.")

# --- aprendidos por tema
st.subheader("Aprendidos por tema")
for tema in banco.temas_ordenados():
    del_tema = {e.id for e in banco.por_tema(tema.id) if e.cuenta_nivel}
    if del_tema:
        hechos = len(aprendidos & del_tema)
        st.progress(hechos / len(del_tema), text=f"{tema.nombre}: {hechos} de {len(del_tema)}")

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

# --- repasos programados
st.subheader("Repasos programados")
if programados:
    st.caption("Entran al ver la solución o al fallar 3 veces seguidas. Se repasan a 1, 3 y 7 días: "
               "resuélvelos sin mirar la solución para avanzar. Si fallas, vuelven a empezar.")
    for r in programados:
        ej = banco.ejercicios[r["ejercicio_id"]]
        toca = r["proxima"] <= hoy
        c1, c2, c3 = st.columns([4, 2.2, 1], vertical_alignment="center")
        c1.markdown(f"**{ej.titulo}**  \n:gray[{banco.temas[ej.tema].nombre} · {ej.concepto}]")
        cuando = repaso.texto_proximo(r["proxima"], hoy)
        paso = f"repaso {r['etapa'] + 1} de {len(repaso.INTERVALOS_DIAS)} (a {repaso.etiqueta_etapa(r['etapa'])})"
        c2.markdown((f":orange[{cuando}]" if toca else cuando) + f"  \n:gray[{paso}]")
        if c3.button("Abrir", key=f"rep_{ej.id}"):
            comun.abrir_ejercicio(ej.id, ej.tema)
            st.switch_page("paginas/practicar.py")
else:
    st.success("No tienes repasos pendientes.")

# --- reinicio
with st.expander("Borrar todo mi progreso"):
    st.warning("Esto elimina intentos, ejercicios aprendidos y racha. No se puede deshacer.")
    if st.checkbox("Entiendo que se borrará todo"):
        if st.button("Borrar progreso", type="primary"):
            prog.reiniciar()
            st.success("Progreso borrado.")
            st.rerun()
