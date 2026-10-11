"""Calendario del repaso espaciado (logica pura, sin base de datos ni Streamlit).

Un ejercicio entra en la cola de repaso cuando ves su solucion o cuando fallas
Comprobar FALLOS_PARA_REPASO veces seguidas sin acertar. Despues se repasa a
1, 3 y 7 dias:

    entra            -> toca a 1 dia            (etapa 0)
    aciertas         -> toca a 3 dias           (etapa 1)
    aciertas         -> toca a 7 dias           (etapa 2)
    aciertas         -> sale de la cola (repaso superado)

Si fallas o ves la solucion en un repaso, vuelve a la etapa 0 (toca al dia siguiente).
"""
from __future__ import annotations

from datetime import date, timedelta

INTERVALOS_DIAS = (1, 3, 7)
FALLOS_PARA_REPASO = 3


def fecha_repaso(desde: date, etapa: int) -> date:
    """Dia en que toca repasar si la etapa empieza en `desde`."""
    return desde + timedelta(days=INTERVALOS_DIAS[etapa])


def etapa_tras_acierto(etapa: int) -> int | None:
    """Etapa siguiente tras repasar bien. None = repaso superado (sale de la cola)."""
    siguiente = etapa + 1
    return siguiente if siguiente < len(INTERVALOS_DIAS) else None


def texto_proximo(proxima: date, hoy: date) -> str:
    """Cuando toca un repaso, en palabras: 'vencido hace 2 días', 'toca hoy', 'mañana', 'en 5 días (17/10)'."""
    dias = (proxima - hoy).days
    if dias < 0:
        return "vencido hace 1 día" if dias == -1 else f"vencido hace {-dias} días"
    if dias == 0:
        return "toca hoy"
    if dias == 1:
        return "mañana"
    return f"en {dias} días ({proxima.day:02d}/{proxima.month:02d})"


def etiqueta_etapa(etapa: int) -> str:
    """Texto para el alumno: cuanto falta tras este repaso."""
    dias = INTERVALOS_DIAS[etapa]
    return f"{dias} día" if dias == 1 else f"{dias} días"
