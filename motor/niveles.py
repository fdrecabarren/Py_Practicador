"""Reglas de niveles.

Un nivel de un tema se SUPERA cuando al menos el 70 % de sus ejercicios estan
aprendidos (resueltos sin haber visto la solucion), y solo si el nivel anterior
tambien esta superado. Un nivel sin ejercicios no bloquea al siguiente.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import config
from .banco import Banco


@dataclass
class EstadoNivel:
    nivel: str
    total: int
    aprendidos: int
    necesarios: int
    superado: bool
    bloqueado: bool

    @property
    def porcentaje(self) -> float:
        return self.aprendidos / self.total if self.total else 1.0


def estado_niveles(banco: Banco, tema: str, aprendidos: set[str], umbral: float = config.UMBRAL_NIVEL) -> list[EstadoNivel]:
    estados: list[EstadoNivel] = []
    anterior_superado = True
    for nivel in config.NIVELES:
        ejercicios = banco.por_tema_y_nivel(tema, nivel)
        total = len(ejercicios)
        ok = sum(1 for e in ejercicios if e.id in aprendidos)
        necesarios = math.ceil(total * umbral - 1e-9) if total else 0
        cumple = total == 0 or ok >= necesarios
        bloqueado = not anterior_superado
        superado = cumple and not bloqueado
        estados.append(EstadoNivel(nivel, total, ok, necesarios, superado, bloqueado))
        anterior_superado = superado
    return estados


def nivel_actual(estados: list[EstadoNivel]) -> str:
    """Primer nivel no superado (el que toca trabajar). Si estan todos, el ultimo."""
    for e in estados:
        if e.total and not e.superado:
            return e.nivel
    return estados[-1].nivel


def esta_bloqueado(banco: Banco, ejercicio_id: str, aprendidos: set[str]) -> bool:
    ej = banco.ejercicios[ejercicio_id]
    if not ej.cuenta_nivel:  # las preguntas tipo test nunca se bloquean
        return False
    for e in estado_niveles(banco, ej.tema, aprendidos):
        if e.nivel == ej.nivel:
            return e.bloqueado
    return False


def siguiente_ejercicio(banco: Banco, tema: str, aprendidos: set[str], *, excluir: str | set[str] | None = None):
    """Primer ejercicio no aprendido y desbloqueado del tema (por nivel y por id).
    `excluir` es un id o un conjunto de ids que no se deben devolver.
    Si todos estan aprendidos (o excluidos) devuelve None."""
    excluidos = {excluir} if isinstance(excluir, str) else set(excluir or ())
    for nivel in config.NIVELES:
        for ej in sorted(banco.por_tema_y_nivel(tema, nivel), key=lambda e: e.id):
            if ej.id in excluidos or ej.id in aprendidos:
                continue
            if not esta_bloqueado(banco, ej.id, aprendidos):
                return ej
    return None
