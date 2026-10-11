"""Arnes que se ejecuta en un PROCESO APARTE (lo lanza ejecutor_python.py).

Uso interno:  python -I harness.py spec.json salida.json

Lee la especificacion (codigo del alumno, solucion de referencia y tests), ejecuta el
codigo, compara resultados y escribe un JSON con el veredicto. Si el codigo falla,
guarda el traceback REAL de Python, recortado a las lineas del codigo del alumno.
"""
import builtins
import contextlib
import io
import json
import linecache
import re
import sys
import traceback
from pathlib import Path

NOMBRE_ALUMNO = "<tu_codigo>"
NOMBRE_SOLUCION = "<solucion>"
LIMITE_SALIDA = 20000


class _Salida(io.StringIO):
    """stdout acotado: evita que un print en bucle llene la memoria."""

    def write(self, texto):
        if self.tell() < LIMITE_SALIDA:
            return super().write(texto)
        return len(texto)


def _formatear_error(exc, nombre_codigo):
    tb = exc.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename != nombre_codigo:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(exc), exc, tb)).rstrip()


def ejecutar(codigo, entrada="", nombre=NOMBRE_ALUMNO):
    """Ejecuta `codigo`. Devuelve (namespace, stdout, traceback_o_None)."""
    linecache.cache[nombre] = (len(codigo), None, codigo.splitlines(True), nombre)
    cola = io.StringIO(entrada)

    def input_falso(prompt=""):
        linea = cola.readline()
        if linea == "":
            raise EOFError("EOF when reading a line (el ejercicio no ha dado más datos de entrada)")
        return linea.rstrip("\n")

    ns = {"__name__": "__main__", "__builtins__": builtins.__dict__.copy()}
    ns["__builtins__"]["input"] = input_falso
    salida = _Salida()
    error = None
    with contextlib.redirect_stdout(salida):
        try:
            exec(compile(codigo, nombre, "exec"), ns)
        except SystemExit:
            pass
        except BaseException as exc:  # noqa: BLE001 - queremos capturar todo lo del alumno
            error = _formatear_error(exc, nombre)
    return ns, salida.getvalue(), error


def _normalizar_salida(texto):
    return texto.split()


def _tokens_iguales(a, b, ignorar_mayusculas):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        try:
            if abs(float(x) - float(y)) <= 1e-6 * max(1.0, abs(float(y))):
                continue
            return False
        except ValueError:
            pass
        if ignorar_mayusculas:
            x, y = x.lower(), y.lower()
        if x != y:
            return False
    return True


def correr(spec):
    sys.path.insert(0, spec["raiz"])
    from motor import comparar as cmp  # noqa: WPS433

    res = {"estado": "ok", "mensajes": [], "traceback": "", "stdout": "", "vista": ""}
    codigo = spec["codigo"]
    solucion = spec.get("solucion", "")
    opciones = spec.get("comparar") or {}

    # ---- Modo "solo ejecutar": enseña salida y resultado, sin corregir ----
    if spec.get("modo") == "ejecutar":
        ns, salida, error = ejecutar(codigo, spec.get("entrada", ""))
        res["stdout"] = salida
        if error:
            res.update(estado="error", traceback=error)
        elif "resultado" in ns:
            res["vista"] = cmp.vista_previa(ns["resultado"])
        return res

    tests = spec.get("tests") or [{"tipo": "resultado"}]
    cache_alumno = {}
    cache_solucion = {}

    def correr_alumno(entrada=""):
        if entrada not in cache_alumno:
            cache_alumno[entrada] = ejecutar(codigo, entrada)
        return cache_alumno[entrada]

    def correr_solucion(entrada=""):
        if entrada not in cache_solucion:
            cache_solucion[entrada] = ejecutar(solucion, entrada, NOMBRE_SOLUCION)
        return cache_solucion[entrada]

    for t in tests:
        tipo = t.get("tipo", "resultado")
        prefijo = f"[{t['descripcion']}] " if t.get("descripcion") else ""
        entrada = t.get("entrada", "") if tipo == "salida" else ""
        ns, salida, error = correr_alumno(entrada)
        res["stdout"] = salida
        if error:
            res.update(estado="error", traceback=error)
            return res

        if tipo == "resultado":
            if "resultado" not in ns:
                res["mensajes"].append(prefijo + "Tu código debe dejar la respuesta en una variable llamada `resultado`.")
                continue
            res["vista"] = cmp.vista_previa(ns["resultado"])
            ns_sol, _, error_sol = correr_solucion()
            if error_sol or "resultado" not in ns_sol:
                res.update(estado="error_banco", traceback=error_sol or "La solución de referencia no define `resultado`.")
                return res
            opc = dict(opciones, **{k: v for k, v in t.items() if k in cmp.OPCIONES_POR_DEFECTO})
            res["mensajes"] += [prefijo + m for m in cmp.comparar(ns["resultado"], ns_sol["resultado"], opc)]

        elif tipo == "funcion":
            nombre = t["nombre"]
            if nombre not in ns or not callable(ns[nombre]):
                res["mensajes"].append(prefijo + f"No encuentro la función `{nombre}`. Define `def {nombre}(...):`.")
                continue
            opc = dict(opciones, **{k: v for k, v in t.items() if k in cmp.OPCIONES_POR_DEFECTO})
            for caso in t.get("casos", []):
                args, kwargs = caso.get("args", []), caso.get("kwargs", {})
                llamada = f"{nombre}({', '.join(map(repr, args))}{', ' if args and kwargs else ''}{', '.join(f'{k}={v!r}' for k, v in kwargs.items())})"
                try:
                    devuelto = ns[nombre](*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001
                    res.update(estado="error", traceback=_formatear_error(exc, NOMBRE_ALUMNO))
                    res["mensajes"].append(prefijo + f"Al llamar a {llamada} tu función falló.")
                    return res
                problemas = cmp.comparar(devuelto, caso["esperado"], opc)
                if problemas:
                    res["mensajes"].append(
                        prefijo + f"{llamada} devolvió {devuelto!r} y se esperaba {caso['esperado']!r}."
                    )
                    break

        elif tipo == "salida":
            esperado = _normalizar_salida(str(t["esperado"]))
            obtenido = _normalizar_salida(salida)
            if not _tokens_iguales(obtenido, esperado, t.get("ignorar_mayusculas", True)):
                con = f" con entrada {entrada.strip().splitlines()!r}" if entrada.strip() else ""
                res["mensajes"].append(
                    prefijo + f"Tu programa{con} imprimió {' '.join(obtenido)!r} y se esperaba {' '.join(esperado)!r}."
                )

        else:
            res.update(estado="error_banco", traceback=f"Tipo de test desconocido: {tipo}")
            return res

    if res["mensajes"]:
        res["estado"] = "fallo"
    return res


def main():
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        res = correr(spec)
    except BaseException:  # noqa: BLE001 - error del arnes, no del alumno
        res = {"estado": "error_banco", "mensajes": [], "traceback": traceback.format_exc(), "stdout": "", "vista": ""}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
