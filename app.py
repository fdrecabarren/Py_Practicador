"""Practicador: app local de practica para el bootcamp de Data Analytics (Factoria F5).

Arranque: doble clic en practicar.bat  (o:  streamlit run app.py)
"""
import streamlit as st

st.set_page_config(page_title="Practicador", layout="wide", initial_sidebar_state="expanded")

paginas = [
    st.Page("paginas/inicio.py", title="Inicio", icon=":material/home:", default=True),
    st.Page("paginas/practicar.py", title="Practicar", icon=":material/edit_note:"),
    st.Page("paginas/progreso.py", title="Mi progreso", icon=":material/monitoring:"),
    st.Page("paginas/ajustes.py", title="Conexión y ajustes", icon=":material/settings:"),
]
pagina = st.navigation(paginas)
st.sidebar.caption("Modo claro u oscuro: menú ⋮ de arriba a la derecha.")
pagina.run()
