@echo off
title Practicador
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo No encuentro el entorno .venv. Ejecuta primero instalar.bat
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
if not exist "datos\kiva_muestra.csv" python scripts\preparar_datos.py
echo Abriendo el Practicador. Cierra esta ventana para detenerlo.
python -m streamlit run app.py
pause
