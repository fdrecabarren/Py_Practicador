"""Sesion de hoy: una tanda de unos 20 minutos que mezcla repasos vencidos y ejercicios nuevos.

Logica pura (sin Streamlit): arma la lista de ejercicios y ayuda a recorrerla.
El estado de la sesion en curso vive en la memoria de la app (st.session_state);
el progreso de cada ejercicio se guarda siempre en la base de datos.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import niveles
from .banco import Banco, Ejercicio

MINUTOS_SESION = 20
MAX_NUEVOS = 2

# Estimacion fija del tiempo de un ejercicio: base por tipo + extra por nivel.
MINUTOS_BASE = {"test": 1, "python": 4, "sql": 4, "excel": 7, "terminal_git": 5}
MINUTOS_NIVEL = {"basico": 0, "intermedio": 3, "junior": 6}


@dataclass(frozen=True)
class ItemSesion:
    ejercicio_id: str
    motivo: str  # "repaso" | "nuevo"


def minutos_estimados(ej: Ejercicio) -> int:
    if ej.tipo == "test":
        return MINUTOS_BASE["test"]
    return MINUTOS_BASE.get(ej.tipo, 5) + MINUTOS_NIVEL.get(ej.nivel, 0)


def _candidatos_nuevos(banco: Banco, prog, excluidos: set[str], max_nuevos: int) -> list[str]:
    """Siguientes ejercicios por estrenar: uno por tema (empezando por el ultimo que practicaste);
    si faltan, una segunda vuelta."""
    aprendidos = prog.aprendidos()
    temas = banco.temas_ordenados()
    ultimo = prog.ultimo_tema()
    if ultimo:
        temas = [t for t in temas if t.id == ultimo] + [t for t in temas if t.id != ultimo]
    elegidos: list[str] = []
    while len(elegidos) < max_nuevos:
        anadido = False
        for t in temas:
            if len(elegidos) >= max_nuevos:
                break
            ej = niveles.siguiente_ejercicio(banco, t.id, aprendidos, excluir=excluidos | set(elegidos))
            if ej is not None:
                elegidos.append(ej.id)
                anadido = True
        if not anadido:
            break
    return elegidos


def armar_sesion(banco: Banco, prog, minutos: int = MINUTOS_SESION, max_nuevos: int = MAX_NUEVOS) -> list[ItemSesion]:
    """Repasos vencidos (los mas atrasados primero) y 1 o 2 ejercicios nuevos de tu nivel,
    intercalados y sin pasarse de `minutos`. Siempre entra al menos un repaso y un nuevo si los hay."""
    vencidos = [r["ejercicio_id"] for r in prog.repasos_vencidos() if r["ejercicio_id"] in banco.ejercicios]
    en_cola = {r["ejercicio_id"] for r in prog.repasos_programados()}
    nuevos = _candidatos_nuevos(banco, prog, en_cola, max_nuevos)

    total = minutos_estimados(banco.ejercicios[nuevos[0]]) if nuevos else 0   # el primer nuevo va reservado
    repasos: list[str] = []
    for ej_id in vencidos:
        m = minutos_estimados(banco.ejercicios[ej_id])
        if not repasos or total + m <= minutos:
            repasos.append(ej_id)
            total += m
    elegidos_nuevos = nuevos[:1]
    for ej_id in nuevos[1:]:
        m = minutos_estimados(banco.ejercicios[ej_id])
        if total + m <= minutos:
            elegidos_nuevos.append(ej_id)
            total += m

    items: list[ItemSesion] = []
    for i in range(max(len(repasos), len(elegidos_nuevos))):
        if i < len(repasos):
            items.append(ItemSesion(repasos[i], "repaso"))
        if i < len(elegidos_nuevos):
            items.append(ItemSesion(elegidos_nuevos[i], "nuevo"))
    return items


def minutos_totales(banco: Banco, items: list[ItemSesion]) -> int:
    return sum(minutos_estimados(banco.ejercicios[i.ejercicio_id]) for i in items)


def posicion(items: list[ItemSesion], ejercicio_id: str | None) -> int | None:
    """Indice del ejercicio dentro de la sesion (None si no es de la sesion)."""
    for n, item in enumerate(items):
        if item.ejercicio_id == ejercicio_id:
            return n
    return None


def siguiente_en_sesion(items: list[ItemSesion], ejercicio_id: str | None) -> str | None:
    n = posicion(items, ejercicio_id)
    return items[n + 1].ejercicio_id if n is not None and n + 1 < len(items) else None


def primer_pendiente(items: list[ItemSesion], hechos: set[str]) -> str | None:
    return next((i.ejercicio_id for i in items if i.ejercicio_id not in hechos), None)


def resumen(items: list[ItemSesion], hechos: set[str]) -> dict:
    """{'total', 'hechos', 'repasos_hechos', 'nuevos_hechos', 'sin_hacer': [ids]}"""
    hechos_items = [i for i in items if i.ejercicio_id in hechos]
    return {
        "total": len(items),
        "hechos": len(hechos_items),
        "repasos_hechos": sum(1 for i in hechos_items if i.motivo == "repaso"),
        "nuevos_hechos": sum(1 for i in hechos_items if i.motivo == "nuevo"),
        "sin_hacer": [i.ejercicio_id for i in items if i.ejercicio_id not in hechos],
    }
