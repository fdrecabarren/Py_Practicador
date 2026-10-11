"""Carga y valida el banco de ejercicios (archivos YAML en ejercicios/).

Cada archivo `ejercicios/<nombre>.yaml` es una lista de ejercicios. El archivo
`ejercicios/_temas.yaml` define los temas (orden, nombre, descripcion, fase).
El formato completo esta explicado en CLAUDE.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config

TIPOS = ("python", "sql", "test", "excel", "terminal_git")
TIPOS_CON_PISTAS = ("python", "sql", "excel", "terminal_git")
TIPOS_TEST_PYTHON = ("resultado", "funcion", "salida")


class ErrorBanco(Exception):
    """El banco tiene ejercicios mal formados. El mensaje lista todos los problemas."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__("Banco de ejercicios invalido:\n- " + "\n- ".join(problemas))


@dataclass
class Tema:
    id: str
    nombre: str
    descripcion: str = ""
    fase: int = 1
    orden: int = 0


@dataclass
class Ejercicio:
    id: str
    tipo: str
    tema: str
    concepto: str
    nivel: str
    titulo: str
    enunciado: str
    origen: str
    explicacion: str = ""
    pistas: list[str] = field(default_factory=list)
    codigo_inicial: str = ""
    solucion: str = ""
    datos: list[str] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    comparar: dict = field(default_factory=dict)
    # preguntas tipo test
    opciones: list[str] = field(default_factory=list)
    correcta: int | None = None
    # ajustes
    timeout: int | None = None
    solo_mysql: bool = False
    nota_dialecto: str = ""
    cuenta_nivel: bool = True
    extra: dict = field(default_factory=dict)  # campos propios de excel / terminal_git
    archivo: str = ""

    @property
    def admite_pistas(self) -> bool:
        return self.tipo in TIPOS_CON_PISTAS


def _validar(d: dict, archivo: str) -> list[str]:
    p: list[str] = []
    ident = d.get("id", "<sin id>")
    pre = f"{archivo}:{ident}"

    for campo in ("id", "tipo", "tema", "concepto", "nivel", "titulo", "enunciado", "origen"):
        if not str(d.get(campo, "")).strip():
            p.append(f"{pre}: falta el campo obligatorio '{campo}'")
    if d.get("tipo") not in TIPOS:
        p.append(f"{pre}: tipo '{d.get('tipo')}' no valido (usa {', '.join(TIPOS)})")
    if d.get("nivel") not in config.NIVELES:
        p.append(f"{pre}: nivel '{d.get('nivel')}' no valido (usa {', '.join(config.NIVELES)})")

    tipo = d.get("tipo")
    if tipo in TIPOS_CON_PISTAS:
        pistas = d.get("pistas") or []
        if len(pistas) != 3 or not all(str(x).strip() for x in pistas):
            p.append(f"{pre}: 'pistas' debe tener exactamente 3 textos (idea general, pista concreta, solucion explicada)")
        if not str(d.get("explicacion", "")).strip():
            p.append(f"{pre}: falta 'explicacion'")
        if tipo in ("python", "sql") and not str(d.get("solucion", "")).strip():
            p.append(f"{pre}: falta 'solucion' (solucion de referencia)")
    if tipo == "python":
        for t in d.get("tests") or []:
            if t.get("tipo", "resultado") not in TIPOS_TEST_PYTHON:
                p.append(f"{pre}: test con tipo '{t.get('tipo')}' desconocido")
            if t.get("tipo") == "funcion" and not (t.get("nombre") and t.get("casos")):
                p.append(f"{pre}: un test 'funcion' necesita 'nombre' y 'casos'")
            if t.get("tipo") == "salida" and "esperado" not in t:
                p.append(f"{pre}: un test 'salida' necesita 'esperado'")
    if tipo == "test":
        ops = d.get("opciones") or []
        if len(ops) < 2:
            p.append(f"{pre}: una pregunta test necesita al menos 2 'opciones'")
        c = d.get("correcta")
        if not isinstance(c, int) or not (0 <= c < max(len(ops), 1)):
            p.append(f"{pre}: 'correcta' debe ser el indice (desde 0) de una opcion")
        if not str(d.get("explicacion", "")).strip():
            p.append(f"{pre}: falta 'explicacion'")
    return p


@dataclass
class Banco:
    temas: dict[str, Tema]
    ejercicios: dict[str, Ejercicio]

    def por_tema(self, tema: str, *, incluir_tests: bool = True) -> list[Ejercicio]:
        res = [e for e in self.ejercicios.values() if e.tema == tema]
        if not incluir_tests:
            res = [e for e in res if e.cuenta_nivel]
        return res

    def por_tema_y_nivel(self, tema: str, nivel: str) -> list[Ejercicio]:
        return [e for e in self.por_tema(tema) if e.nivel == nivel and e.cuenta_nivel]

    def temas_ordenados(self, fase_max: int | None = None) -> list[Tema]:
        ts = sorted(self.temas.values(), key=lambda t: (t.orden, t.id))
        return [t for t in ts if fase_max is None or t.fase <= fase_max]


def cargar_banco(directorio: Path | None = None) -> Banco:
    directorio = Path(directorio or config.DIR_EJERCICIOS)
    problemas: list[str] = []

    temas: dict[str, Tema] = {}
    ruta_temas = directorio / "_temas.yaml"
    if ruta_temas.exists():
        for t in yaml.safe_load(ruta_temas.read_text(encoding="utf-8")) or []:
            temas[t["id"]] = Tema(**t)

    ejercicios: dict[str, Ejercicio] = {}
    for ruta in sorted(directorio.glob("*.yaml")):
        if ruta.name.startswith("_"):
            continue
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []
        except yaml.YAMLError as exc:
            problemas.append(f"{ruta.name}: YAML mal formado: {exc}")
            continue
        if not isinstance(datos, list):
            problemas.append(f"{ruta.name}: debe contener una lista de ejercicios")
            continue
        for d in datos:
            errs = _validar(d, ruta.name)
            problemas += errs
            if errs:
                continue
            if d["id"] in ejercicios:
                problemas.append(f"{ruta.name}:{d['id']}: id repetido (ya existe en {ejercicios[d['id']].archivo})")
                continue
            if d["tema"] not in temas:
                problemas.append(f"{ruta.name}:{d['id']}: el tema '{d['tema']}' no esta en _temas.yaml")
                continue
            conocidos = Ejercicio.__dataclass_fields__.keys()
            campos = {k: v for k, v in d.items() if k in conocidos and k != "extra"}
            extra = {k: v for k, v in d.items() if k not in conocidos}
            ej = Ejercicio(**campos, extra=extra, archivo=ruta.name)
            if ej.tipo == "test":
                ej.cuenta_nivel = False
            ejercicios[ej.id] = ej

    if problemas:
        raise ErrorBanco(problemas)
    return Banco(temas=temas, ejercicios=ejercicios)
