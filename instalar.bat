@echo off
title Practicador - instalacion
cd /d "%~dp0"
echo === Instalacion del Practicador (solo la primera vez) ===
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual .venv ...
    py -3.13 -m venv .venv
    if errorlevel 1 python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Se ha creado .env. Edita DB_USER y DB_PASSWORD antes de usar SQL.
)
python scripts\preparar_datos.py
echo.
echo Listo. Ya puedes abrir practicar.bat
pause
