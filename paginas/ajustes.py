import subprocess
import sys

import streamlit as st

from motor import config, sql
from paginas import comun

banco = comun.get_banco()

st.title("Conexión y ajustes")

# ---------------------------------------------------------------- MySQL
st.subheader("MySQL (base olist)")
hay_credenciales = sql.url_mysql() is not None
st.markdown(
    f"- Servidor: `{config.DB_HOST}:{config.DB_PORT}`\n"
    f"- Base de datos: `{config.DB_NAME}`\n"
    f"- Usuario: `{config.DB_USER or '(sin configurar)'}`\n"
    f"- Contraseña: {'configurada en `.env`' if config.DB_PASSWORD else '(sin configurar)'}"
)
if not hay_credenciales:
    st.warning("Faltan `DB_USER` y/o `DB_PASSWORD`. Las credenciales se leen del archivo `.env` (nunca del código).", icon=":material/key_off:")
    with st.expander("Cómo configurarlo (2 minutos)", expanded=True):
        st.markdown(
            "1. En MySQL Workbench, abre `scripts/usuario_mysql.sql`, cambia la contraseña y ejecútalo con tu usuario `root`. "
            "Crea un usuario `practicador` que **solo puede leer** la base `olist`.\n"
            "2. Copia `.env.example` como `.env` y escribe esa contraseña en `DB_PASSWORD`.\n"
            "3. Vuelve aquí y pulsa **Recargar conexión**."
        )
if st.button("Probar conexión", disabled=not hay_credenciales, icon=":material/wifi_tethering:"):
    try:
        ok, mensaje = sql.probar_conexion(comun.get_engine())
    except Exception as exc:  # noqa: BLE001
        ok, mensaje = False, str(exc)
    if ok:
        esquema = comun.get_esquema()
        st.success(f"Conexión correcta. Tablas encontradas: {', '.join(esquema) or '(ninguna)'}")
    else:
        st.error("No he podido conectar:")
        st.code(mensaje, language="text")
if st.button("Recargar conexión", icon=":material/refresh:"):
    comun.get_engine.clear()
    comun.get_esquema.clear()
    st.rerun()

# ---------------------------------------------------------------- datos
st.divider()
st.subheader("Datasets de práctica")
usados = sorted({d for e in banco.ejercicios.values() for d in e.datos})
faltan = []
for d in usados:
    existe = (config.DIR_DATOS / d).exists()
    st.markdown(f"- {':green[:material/check_circle:]' if existe else ':red[:material/cancel:]'} `{d}`")
    if not existe:
        faltan.append(d)
if faltan:
    st.warning("Faltan datasets. Vienen incluidos en el repositorio: actualiza con `git pull` o vuelve a descargar el proyecto.")
st.caption(f"Carpeta del curso: `{config.DIR_CURSO}`")
if st.button("Preparar datos ahora", icon=":material/database:"):
    with st.spinner("Preparando datasets..."):
        proc = subprocess.run([sys.executable, str(config.RAIZ / "scripts" / "preparar_datos.py")],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=config.RAIZ)
    st.code(proc.stdout + proc.stderr, language="text")
    if proc.returncode == 0:
        st.rerun()

# ---------------------------------------------------------------- banco
st.divider()
st.subheader("Banco de ejercicios")
st.markdown(
    f"{len([e for e in banco.ejercicios.values() if e.tipo != 'test'])} ejercicios y "
    f"{len([e for e in banco.ejercicios.values() if e.tipo == 'test'])} preguntas rápidas, en `ejercicios/*.yaml`."
)
if st.button("Recargar banco", icon=":material/refresh:"):
    comun.recargar_todo()
    st.rerun()
st.caption("Para añadir ejercicios, mira `CLAUDE.md` y el README. Después de editar los YAML, recarga el banco.")
