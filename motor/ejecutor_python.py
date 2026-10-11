"""Ejecuta el codigo Python del alumno en un proceso aparte, con timeout.

El codigo nunca corre dentro de Streamlit: se lanza `harness.py` con el mismo
interprete del venv, en una carpeta temporal que solo contiene los datasets del
ejercicio. Si pasa el tiempo limite, se mata el proceso.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config

HARNESS = Path(__file__).with_name("harness.py")
_PREFIJOS_SECRETOS = ("DB_", "MYSQL")


def _entorno_limpio() -> dict:
    """Entorno para el proceso hijo, sin las credenciales de .env."""
    return {k: v for k, v in os.environ.items() if not k.startswith(_PREFIJOS_SECRETOS)}


def ejecutar_python(
    codigo: str,
    *,
    solucion: str = "",
    tests: list | None = None,
    comparar: dict | None = None,
    datos: list[str] | None = None,
    modo: str = "comprobar",
    entrada: str = "",
    timeout: int | None = None,
    dir_datos: Path | None = None,
) -> dict:
    """Devuelve un dict con: estado (ok|fallo|error|timeout|error_banco|sin_datos),
    mensajes, traceback, stdout y vista."""
    timeout = timeout or config.TIMEOUT_PYTHON
    dir_datos = Path(dir_datos or config.DIR_DATOS)

    faltan = [d for d in (datos or []) if not (dir_datos / d).exists()]
    if faltan:
        return {
            "estado": "sin_datos",
            "mensajes": [f"Faltan datasets: {', '.join(faltan)}. Ejecuta `python scripts/preparar_datos.py`."],
            "traceback": "", "stdout": "", "vista": "",
        }

    with tempfile.TemporaryDirectory(prefix="practicador_") as tmp:
        tmp = Path(tmp)
        for d in datos or []:
            shutil.copyfile(dir_datos / d, tmp / d)
        spec = {
            "raiz": str(config.RAIZ),
            "codigo": codigo,
            "solucion": solucion,
            "tests": tests or [],
            "comparar": comparar or {},
            "modo": modo,
            "entrada": entrada,
        }
        spec_path, out_path = tmp / "_spec.json", tmp / "_resultado.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(HARNESS), str(spec_path), str(out_path)],
                cwd=tmp, env=_entorno_limpio(), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "estado": "timeout",
                "mensajes": [
                    f"Tu código tardó más de {timeout} segundos y lo he detenido. "
                    "Revisa si hay un bucle que no termina (por ejemplo un `while True` sin `break`)."
                ],
                "traceback": "", "stdout": "", "vista": "",
            }
        if not out_path.exists():
            return {
                "estado": "error_banco",
                "mensajes": [],
                "traceback": (proc.stderr or "El proceso terminó sin dar resultado.")[-3000:],
                "stdout": "", "vista": "",
            }
        return json.loads(out_path.read_text(encoding="utf-8"))
