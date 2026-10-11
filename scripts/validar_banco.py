"""Valida el banco de ejercicios: que no haya ejercicios rotos.

Uso (con el venv activo):
    python scripts/validar_banco.py                 # todo el banco
    python scripts/validar_banco.py --tema pandas   # solo un tema
    python scripts/validar_banco.py --id pd-003     # un ejercicio
    python scripts/validar_banco.py --sql sqlite    # SQL contra el mini-Olist de pruebas
    python scripts/validar_banco.py --sql mysql     # SQL contra tu MySQL (.env)

Comprueba para cada ejercicio:
  python : la solucion de referencia pasa sus tests; el codigo inicial NO los pasa;
           existen los datasets; la pista 1 no contiene la solucion literal.
  sql    : la solucion es una consulta valida y de solo lectura, se ejecuta sin error
           y devuelve filas; el SQL inicial no resuelve el ejercicio.
  excel  : el libro de partida NO pasa las comprobaciones; el libro resuelto (generado con lo que
           piden las comprobaciones) SI las pasa; la pista 1 no nombra la funcion que hay que usar.
  terminal_git : tras `preparar` las comprobaciones NO pasan; tras ejecutar la `solucion` SI las pasan
           (se ejecuta en una carpeta temporal con Git Bash real).
  test   : la opcion correcta existe y las opciones no estan repetidas.
Sale con codigo 1 si hay algun fallo (util antes de hacer commit).
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from motor import excel as motor_excel  # noqa: E402
from motor import sql as motor_sql  # noqa: E402
from motor import terminal as motor_terminal  # noqa: E402
from motor.banco import ErrorBanco, cargar_banco  # noqa: E402
from motor.ejecutor_python import ejecutar_python  # noqa: E402


def _filas_literales(texto: str) -> list[str]:
    return [l.strip() for l in texto.splitlines() if len(l.strip()) >= 18 and not l.strip().startswith(("#", "--"))]


def _pistas_filtran_solucion(ej) -> str | None:
    if not ej.solucion:
        return None
    for fila in _filas_literales(ej.solucion):
        for i, pista in enumerate(ej.pistas[:1], start=1):
            if fila in pista:
                return f"la pista {i} contiene la linea de la solucion: {fila!r}"
    return None


def validar_python(ej):
    fallos, avisos = [], []
    r = ejecutar_python(
        ej.solucion, solucion=ej.solucion, tests=ej.tests, comparar=ej.comparar,
        datos=ej.datos, timeout=ej.timeout or 30,
    )
    if r["estado"] != "ok":
        detalle = " | ".join(r["mensajes"]) or r["traceback"][-400:] or r["estado"]
        fallos.append(f"la solucion de referencia NO pasa sus tests ({r['estado']}): {detalle}")
    if ej.codigo_inicial.strip():
        r0 = ejecutar_python(
            ej.codigo_inicial, solucion=ej.solucion, tests=ej.tests, comparar=ej.comparar,
            datos=ej.datos, timeout=ej.timeout or 30,
        )
        if r0["estado"] == "ok":
            fallos.append("el codigo inicial YA pasa los tests (el ejercicio no plantea nada que resolver)")
    filtra = _pistas_filtran_solucion(ej)
    if filtra:
        avisos.append(filtra)
    return fallos, avisos


def validar_sql(ej, engine, modo):
    fallos, avisos = [], []
    if ej.solo_mysql and modo == "sqlite":
        return fallos, ["saltado: solo_mysql (se valida con --sql mysql)"]
    problema, _ = motor_sql.validar_consulta(ej.solucion)
    if problema:
        return [f"la solucion no es una consulta permitida: {problema}"], avisos
    v = motor_sql.corregir_sql(
        engine, ej.solucion, ej.solucion,
        ordenado=bool(ej.comparar.get("ordenado")), alias=bool(ej.comparar.get("alias")),
    )
    if v["estado"] != "ok":
        fallos.append(f"la solucion falla ({v['estado']}): {v['error'] or v['mensajes']}")
    elif v["n_filas"] == 0:
        avisos.append("la solucion devuelve 0 filas (con el mini-Olist puede ser normal; revisalo con MySQL)")
    if ej.codigo_inicial.strip():
        v0 = motor_sql.corregir_sql(
            engine, ej.codigo_inicial, ej.solucion,
            ordenado=bool(ej.comparar.get("ordenado")), alias=bool(ej.comparar.get("alias")),
        )
        if v0["estado"] == "ok":
            fallos.append("el SQL inicial YA resuelve el ejercicio")
    filtra = _pistas_filtran_solucion(ej)
    if filtra:
        avisos.append(filtra)
    return fallos, avisos


def _nombres_exigidos(ej) -> list[str]:
    """Funciones o referencias que las comprobaciones exigen en las formulas."""
    res = []
    for c in ej.comprobaciones:
        if isinstance(c.get("formula"), str):
            res.append(c["formula"])
        res += [str(x) for x in c.get("formula_contiene", [])]
    return res


def validar_excel(ej):
    fallos, avisos = [], []
    try:
        partida = motor_excel.generar_libro(ej)
        r0 = motor_excel.corregir_excel(ej, partida)
        if r0["estado"] == "error_banco":
            return [f"el ejercicio esta mal definido: {' | '.join(r0['mensajes'])}"], avisos
        if r0["estado"] == "ok":
            fallos.append("el libro de partida YA pasa las comprobaciones (no hay nada que resolver)")
        resuelto = motor_excel.libro_resuelto(ej)
        r1 = motor_excel.corregir_excel(ej, resuelto)
        if r1["estado"] != "ok":
            fallos.append(f"el libro resuelto NO pasa ({r1['estado']}): {' | '.join(r1['mensajes'])}")
        for c in r1["comprobaciones"]:
            if not c["ok"] and c["blando"]:
                avisos.append(f"comprobacion blanda no cumplida con el libro sintetico: {c['titulo']}")
    except motor_excel.ErrorExcel as exc:
        return [str(exc)], avisos
    pista1 = ej.pistas[0].casefold() if ej.pistas else ""
    for nombre in _nombres_exigidos(ej):
        if len(nombre) >= 3 and nombre.casefold() in pista1:
            avisos.append(f"la pista 1 nombra lo que hay que usar: {nombre!r}")
    return fallos, avisos


def validar_terminal(ej):
    fallos, avisos = [], []
    if motor_terminal.encontrar_bash() is None or motor_terminal.encontrar_git() is None:
        return fallos, ["saltado: hace falta Git for Windows (git y bash)"]
    with tempfile.TemporaryDirectory(prefix="practicador_val_") as tmp:
        sandbox = Path(tmp) / "sandbox"
        try:
            prep = motor_terminal.preparar(ej, sandbox)
            if not prep["ok"]:
                return [prep["error"]], avisos
            r0 = motor_terminal.comprobar(ej, sandbox)
            if r0["estado"] == "error_banco":
                return [f"comprobaciones mal definidas: {' | '.join(r0['mensajes'])}"], avisos
            if r0["estado"] == "ok":
                fallos.append("tras preparar, las comprobaciones YA pasan (no hay nada que resolver)")
            ok, salida = motor_terminal.resolver(ej, sandbox)
            if not ok:
                return fallos + [f"la solucion falla al ejecutarse: {salida}"], avisos
            r1 = motor_terminal.comprobar(ej, sandbox)
            if r1["estado"] != "ok":
                fallos.append(f"tras la solucion las comprobaciones NO pasan: {' | '.join(r1['mensajes'])}")
        except motor_terminal.ErrorTerminal as exc:
            fallos.append(str(exc))
    pista1 = ej.pistas[0] if ej.pistas else ""
    for linea in (l.strip() for l in ej.solucion.splitlines()):
        if len(linea) >= 12 and not linea.startswith("#") and linea in pista1:
            avisos.append(f"la pista 1 contiene la linea de la solucion: {linea!r}")
    return fallos, avisos


def validar_test(ej):
    fallos = []
    if len(set(ej.opciones)) != len(ej.opciones):
        fallos.append("hay opciones repetidas")
    return fallos, []


def elegir_engine(modo):
    if modo == "sqlite":
        from motor.fixture_olist import crear_fixture, engine_fixture
        ruta = Path(tempfile.gettempdir()) / "practicador_olist_fixture.db"
        crear_fixture(ruta)
        return engine_fixture(ruta), "sqlite"
    if modo == "mysql":
        engine = motor_sql.crear_engine()
        ok, msg = motor_sql.probar_conexion(engine)
        if not ok:
            raise SystemExit(f"No puedo conectar a MySQL: {msg}")
        return engine, "mysql"
    return None, "ninguno"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tema")
    ap.add_argument("--id")
    ap.add_argument("--sql", choices=["auto", "mysql", "sqlite", "saltar"], default="auto")
    args = ap.parse_args()

    try:
        banco = cargar_banco()
    except ErrorBanco as exc:
        print(exc)
        return 1

    ejercicios = [
        e for e in banco.ejercicios.values()
        if (not args.tema or e.tema == args.tema) and (not args.id or e.id == args.id)
    ]
    modo = args.sql
    if modo == "auto":
        modo = "mysql" if motor_sql.url_mysql() else "sqlite"
    engine = None
    if any(e.tipo == "sql" for e in ejercicios) and modo != "saltar":
        engine, modo = elegir_engine(modo)
        print(f"[SQL] validando contra: {modo}")

    def validar(ej):
        if ej.tipo == "python":
            return ej, *validar_python(ej)
        if ej.tipo == "sql":
            if modo == "saltar":
                return ej, [], ["saltado (--sql saltar)"]
            return ej, *validar_sql(ej, engine, modo)
        if ej.tipo == "excel":
            return ej, *validar_excel(ej)
        if ej.tipo == "terminal_git":
            return ej, *validar_terminal(ej)
        if ej.tipo == "test":
            return ej, *validar_test(ej)
        return ej, [], [f"tipo '{ej.tipo}' sin validador"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(validar, ejercicios))

    n_fallos = 0
    for ej, fallos, avisos in sorted(resultados, key=lambda r: (r[0].tema, r[0].id)):
        marca = "FALLO" if fallos else "ok   "
        print(f"{marca}  {ej.id:<8} {ej.tema:<14} {ej.nivel:<10} {ej.titulo}")
        for f in fallos:
            print(f"        ERROR: {f}")
        for a in avisos:
            print(f"        aviso: {a}")
        n_fallos += bool(fallos)

    por_tema: dict[str, int] = {}
    for ej in ejercicios:
        por_tema[ej.tema] = por_tema.get(ej.tema, 0) + 1
    print(f"\n{len(ejercicios)} ejercicios revisados ({', '.join(f'{t}: {n}' for t, n in sorted(por_tema.items()))}); "
          f"{n_fallos} con errores.")
    return 1 if n_fallos else 0


if __name__ == "__main__":
    sys.exit(main())
