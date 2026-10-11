"""Rutas y ajustes del proyecto. Las credenciales salen siempre de .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DIR_EJERCICIOS = RAIZ / "ejercicios"
DIR_DATOS = RAIZ / "datos"
DIR_PROGRESO = RAIZ / "progreso"
DIR_SANDBOX = RAIZ / "sandbox"
DB_PROGRESO = Path(os.getenv("PRACTICADOR_DB", DIR_PROGRESO / "progreso.db"))

# Carpeta del curso: por defecto, la que contiene a practicador (E:\Data_Analytic)
DIR_CURSO = Path(os.getenv("CURSO_DIR", RAIZ.parent))

# Conexion MySQL (nombres iguales que en el proyecto de Olist del curso)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "olist")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

TIMEOUT_PYTHON = int(os.getenv("TIMEOUT_PYTHON", "15"))
TIMEOUT_SQL = int(os.getenv("TIMEOUT_SQL", "15"))

# Reglas de aprendizaje
UMBRAL_NIVEL = 0.70
NIVELES = ("basico", "intermedio", "junior")
NOMBRE_NIVEL = {"basico": "Básico", "intermedio": "Intermedio", "junior": "Junior"}
