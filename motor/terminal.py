"""Ejercicios de Terminal y Git.

Cada ejercicio trabaja en su propia carpeta dentro del proyecto:

    sandbox/<id>/trabajo/    carpeta donde el alumno abre Git Bash
    sandbox/<id>/remoto.git  remoto local (solo si el ejercicio lo pide)

Reglas de seguridad:
- Nunca se toca nada fuera de `sandbox/<id>`. Antes de borrar se comprueba la ruta.
- Git NO puede subir hasta el repo del propio proyecto (ni hasta ningun repo real):
  se fija GIT_CEILING_DIRECTORIES a la raiz de practicador, tanto en las
  comprobaciones como en el Git Bash que abre la app.
- Las comprobaciones solo ejecutan comandos de LECTURA de Git (lista blanca).
- El script `preparar` y la `solucion` son del banco de ejercicios (de confianza);
  los comandos del alumno los escribe el alumno en su propio Git Bash.
- Las credenciales de .env (DB_*) no se pasan a ningun proceso.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path

from . import config

TIMEOUT = 60
ID_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Subcomandos de Git que solo leen. Los marcados con argumentos permitidos exigen alguno de ellos.
GIT_LECTURA = {
    "rev-parse", "log", "status", "ls-files", "diff", "show", "cat-file", "rev-list", "ls-tree", "check-ignore",
    "for-each-ref", "merge-base", "reflog", "describe", "shortlog", "symbolic-ref", "count-objects", "blame",
    "name-rev", "show-ref", "grep", "diff-tree", "ls-remote", "whatchanged",
}
GIT_LECTURA_CON_FLAG = {
    "branch": {"--list", "-l", "--show-current", "-a", "-r", "-v", "-vv", "--merged", "--no-merged", "--contains"},
    "tag": {"--list", "-l", "--contains"},
    "remote": {"-v", "get-url"},
    "config": {"--get", "--get-all", "--list", "-l"},
    "stash": {"list"},
}
GIT_PROHIBIDOS = {"-d", "-D", "-m", "-M", "-c", "-C", "--delete", "-f", "--force", "--set-upstream-to", "-u",
                  "--unset-upstream", "--edit-description", "--add", "--unset", "--replace-all"}


class ErrorTerminal(Exception):
    """Fallo al preparar o comprobar un ejercicio de terminal."""


# ================================================================ herramientas
def encontrar_git() -> str | None:
    return shutil.which("git")


def encontrar_bash() -> Path | None:
    """bash.exe de Git for Windows (no el de WSL, que vive en System32). En otros SO, bash."""
    if os.name != "nt":
        ruta = shutil.which("bash")
        return Path(ruta) if ruta else None
    candidatos = []
    git = encontrar_git()
    if git:
        raiz = Path(git).resolve().parent.parent   # ...\Git\cmd\git.exe -> ...\Git
        candidatos += [raiz / "bin" / "bash.exe", raiz.parent / "bin" / "bash.exe"]
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            candidatos += [Path(base) / "Git" / "bin" / "bash.exe", Path(base) / "Programs" / "Git" / "bin" / "bash.exe"]
    return next((c for c in candidatos if c.exists()), None)


def encontrar_git_bash_gui() -> Path | None:
    bash = encontrar_bash()
    if bash is None:
        return None
    exe = bash.parent.parent / "git-bash.exe"
    return exe if exe.exists() else None


def dir_base(ej_id: str, sandbox: Path | None = None) -> Path:
    if not ID_VALIDO.match(ej_id):
        raise ErrorTerminal(f"Identificador de ejercicio no valido: {ej_id!r}")
    return Path(sandbox or config.DIR_SANDBOX) / ej_id


def dir_trabajo(ej_id: str, sandbox: Path | None = None) -> Path:
    return dir_base(ej_id, sandbox) / "trabajo"


def _barra(p: Path) -> str:
    return str(p).replace("\\", "/")


def entorno(ej_id: str, sandbox: Path | None = None, *, con_identidad: bool = True) -> dict[str, str]:
    """Entorno de los procesos que lanza la app: sin credenciales y con Git encerrado en practicador."""
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("DB_", "MYSQL")) and k.upper() not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    base = dir_base(ej_id, sandbox)
    vacio = base / "gitconfig_vacio"
    env.update({
        "GIT_CEILING_DIRECTORIES": _barra(config.RAIZ if sandbox is None else Path(sandbox).resolve().parent),
        "CHERE_INVOKING": "1",
        "DATOS": _barra(config.DIR_DATOS),
    })
    if con_identidad:   # scripts de la app: aislados de la configuracion del alumno y sin editores ni preguntas
        base.mkdir(parents=True, exist_ok=True)
        vacio.write_text("", encoding="utf-8")
        env.update({
            "GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": "true", "GIT_MERGE_AUTOEDIT": "no",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": _barra(vacio),
            "GIT_AUTHOR_NAME": "Practicador", "GIT_AUTHOR_EMAIL": "practicador@example.invalid",
            "GIT_COMMITTER_NAME": "Practicador", "GIT_COMMITTER_EMAIL": "practicador@example.invalid",
        })
    return env


def _borrar_arbol(ruta: Path, raiz_permitida: Path) -> None:
    ruta, raiz = ruta.resolve(), raiz_permitida.resolve()
    if ruta == raiz or raiz not in ruta.parents:
        raise ErrorTerminal(f"Me niego a borrar {ruta}: no esta dentro de {raiz}")

    def quitar_solo_lectura(func, path, _exc):   # los objetos de .git son de solo lectura en Windows
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if ruta.exists():
        shutil.rmtree(ruta, onerror=quitar_solo_lectura)


def ejecutar_script(script: str, cwd: Path, env: dict[str, str]) -> tuple[bool, str]:
    """Ejecuta un script de bash (lineas de comandos) en `cwd`. Devuelve (ok, salida)."""
    bash = encontrar_bash()
    if bash is None:
        raise ErrorTerminal("No encuentro Git Bash. Instala Git for Windows (https://git-scm.com/downloads).")
    try:
        p = subprocess.run([str(bash), "-l", "-c", "set -e\n" + script], cwd=str(cwd), env=env, capture_output=True,
                           timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"El script tardo mas de {TIMEOUT} s y se detuvo."
    salida = (p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")).strip()
    return p.returncode == 0, salida


# ================================================================= preparar
def preparar(ej, sandbox: Path | None = None) -> dict:
    """Deja la carpeta de trabajo como la pide el ejercicio (borra el intento anterior)."""
    raiz = Path(sandbox or config.DIR_SANDBOX)
    base = dir_base(ej.id, sandbox)
    raiz.mkdir(parents=True, exist_ok=True)
    _borrar_arbol(base, raiz)
    trabajo = base / "trabajo"
    trabajo.mkdir(parents=True)
    env = entorno(ej.id, sandbox)
    if ej.remoto:
        ok, salida = ejecutar_script("git init --bare -q -b main remoto.git", base, env)
        if not ok:
            return {"ok": False, "error": f"No pude crear el remoto local: {salida}", "carpeta": trabajo}
    if ej.preparar.strip():
        ok, salida = ejecutar_script(ej.preparar, trabajo, env)
        if not ok:
            return {"ok": False, "error": f"Fallo al montar el ejercicio: {salida}", "carpeta": trabajo}
    return {"ok": True, "error": "", "carpeta": trabajo}


def esta_preparado(ej_id: str, sandbox: Path | None = None) -> bool:
    return dir_trabajo(ej_id, sandbox).is_dir()


def resolver(ej, sandbox: Path | None = None) -> tuple[bool, str]:
    """Ejecuta la solucion de referencia (solo para validar el banco y para los tests)."""
    return ejecutar_script(ej.solucion, dir_trabajo(ej.id, sandbox), entorno(ej.id, sandbox))


# =============================================================== comprobar
def _git_permitido(args: list[str]) -> str | None:
    """None si el comando es de solo lectura; si no, el motivo del rechazo."""
    if not args:
        return "comando vacio"
    sub, resto = args[0], args[1:]
    if sub in GIT_LECTURA:
        return None
    if sub in GIT_LECTURA_CON_FLAG:
        if not any(a in GIT_LECTURA_CON_FLAG[sub] for a in resto) and not (sub == "remote" and not resto):
            return f"git {sub} solo se permite con {', '.join(sorted(GIT_LECTURA_CON_FLAG[sub]))}"
        if any(a in GIT_PROHIBIDOS for a in resto):
            return f"git {sub} con ese argumento puede modificar el repositorio"
        return None
    return f"git {sub} no es un comando de solo lectura"


def ejecutar_git(args: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    motivo = _git_permitido(args)
    if motivo:
        raise ErrorTerminal(f"Comprobacion no permitida: {motivo}")
    git = encontrar_git()
    if git is None:
        raise ErrorTerminal("No encuentro git en el PATH. Instala Git for Windows.")
    p = subprocess.run([git, "--no-pager", *args], cwd=str(cwd), env=env, capture_output=True, timeout=TIMEOUT,
                       stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def _normalizar(texto: str) -> list[str]:
    return [" ".join(l.split()) for l in texto.splitlines() if l.strip()]


def _como_lista(v) -> list[str]:
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def _evaluar_criterios(c: dict, salida: str) -> str | None:
    """None si la salida cumple los criterios; si no, que criterio falla."""
    if "igual" in c and salida.strip() != str(c["igual"]).strip():
        return "igual"
    if "igual_normalizado" in c and _normalizar(salida) != _normalizar(str(c["igual_normalizado"])):
        return "igual_normalizado"
    if "contiene" in c and any(t not in salida for t in _como_lista(c["contiene"])):
        return "contiene"
    if "no_contiene" in c and any(t in salida for t in _como_lista(c["no_contiene"])):
        return "no_contiene"
    if "lineas" in c and len([l for l in salida.splitlines() if l.strip()]) != int(c["lineas"]):
        return "lineas"
    if "regex" in c and not re.search(c["regex"], salida, re.M):
        return "regex"
    return None


def _ruta_segura(trabajo: Path, rel: str) -> Path:
    destino = (trabajo / rel).resolve()
    if trabajo.resolve() != destino and trabajo.resolve() not in destino.parents:
        raise ErrorTerminal(f"La comprobacion apunta fuera de la carpeta de trabajo: {rel}")
    return destino


def _comp_archivo(c: dict, trabajo: Path) -> tuple[bool, str]:
    ruta = _ruta_segura(trabajo, c["archivo"])
    quiere_existir = c.get("existe", True)
    if c.get("carpeta"):
        return ruta.is_dir() == quiere_existir, "carpeta"
    if "existe" in c and not any(k in c for k in ("contiene", "no_contiene", "igual", "igual_normalizado", "lineas", "regex")):
        return ruta.exists() == quiere_existir, "existe"
    if not ruta.is_file():
        return False, "existe"
    texto = ruta.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    fallo = _evaluar_criterios(c, texto)
    return fallo is None, fallo or ""


def _titulo(c: dict) -> str:
    if c.get("titulo"):
        return c["titulo"]
    return f"Archivo o carpeta «{c['archivo']}»" if "archivo" in c else f"Resultado de git {c['git']}"


def comprobar(ej, sandbox: Path | None = None) -> dict:
    """Corrige el estado de la carpeta de trabajo. Devuelve {estado, comprobaciones, mensajes}."""
    if not esta_preparado(ej.id, sandbox):
        return {"estado": "sin_preparar", "comprobaciones": [],
                "mensajes": ["Primero pulsa «Preparar ejercicio» para crear la carpeta de trabajo."]}
    trabajo = dir_trabajo(ej.id, sandbox)
    env = entorno(ej.id, sandbox)
    resultados = []
    for c in ej.comprobaciones:
        titulo = _titulo(c)
        pista = c.get("mensaje") or "Revisa este punto del enunciado."
        try:
            if "archivo" in c:
                ok, _ = _comp_archivo(c, trabajo)
                resultados.append({"ok": ok, "titulo": titulo, "mensaje": "" if ok else pista, "blando": False})
            else:
                args = shlex.split(c["git"])
                codigo, salida = ejecutar_git(args, trabajo, env)
                if codigo != 0 and not c.get("permitir_error"):
                    ok, msg = False, "Todavía no hay nada que comprobar con Git aquí (¿ya iniciaste el repositorio?). " + pista
                else:
                    ok = _evaluar_criterios(c, salida) is None
                    msg = pista
                resultados.append({"ok": ok, "titulo": titulo, "mensaje": "" if ok else msg, "blando": False})
        except ErrorTerminal as exc:
            return {"estado": "error_banco", "comprobaciones": resultados, "mensajes": [str(exc)]}
        except subprocess.TimeoutExpired:
            return {"estado": "error", "comprobaciones": resultados, "mensajes": ["Git tardó demasiado en responder."]}
    fallos = [r for r in resultados if not r["ok"]]
    return {"estado": "fallo" if fallos else "ok", "comprobaciones": resultados,
            "mensajes": [f"{r['titulo']}: {r['mensaje']}" for r in fallos]}


# ============================================================ ver estado / abrir
def estado_repo(ej, sandbox: Path | None = None) -> str:
    """Resumen de solo lectura de la carpeta de trabajo (lo que veria el alumno con ls / git status / git log)."""
    if not esta_preparado(ej.id, sandbox):
        return "La carpeta de trabajo todavía no existe. Pulsa «Preparar ejercicio»."
    trabajo = dir_trabajo(ej.id, sandbox)
    env = entorno(ej.id, sandbox)
    partes = ["$ ls -A"]
    nombres = sorted(p.name + ("/" if p.is_dir() else "") for p in trabajo.iterdir() if p.name != ".git")
    partes.append("\n".join(nombres) or "(vacía)")
    codigo, _ = ejecutar_git(["rev-parse", "--is-inside-work-tree"], trabajo, env)
    if codigo != 0:
        partes.append("\n(no es un repositorio Git)")
        return "\n".join(partes)
    for titulo, args in (("git status -sb", ["status", "-sb"]),
                         ("git log --oneline --graph --all", ["log", "--oneline", "--graph", "--all"])):
        codigo, salida = ejecutar_git(args, trabajo, env)
        partes.append(f"\n$ {titulo}\n{salida.strip() or '(sin commits todavía)'}")
    return "\n".join(partes)


def abrir_git_bash(ej_id: str, sandbox: Path | None = None) -> tuple[bool, str]:
    """Abre Git Bash en la carpeta de trabajo (Windows). El Git del alumno queda encerrado en practicador."""
    trabajo = dir_trabajo(ej_id, sandbox)
    if not trabajo.is_dir():
        return False, "La carpeta de trabajo todavía no existe."
    exe = encontrar_git_bash_gui()
    if exe is None:
        return False, "No encuentro Git Bash. Abre tu terminal y entra en la carpeta con cd."
    env = entorno(ej_id, sandbox, con_identidad=False)
    try:
        subprocess.Popen([str(exe)], cwd=str(trabajo), env=env, close_fds=True)
    except OSError as exc:
        return False, f"No pude abrir Git Bash: {exc}"
    return True, ""
