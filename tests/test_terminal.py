import subprocess

import pytest

from motor import terminal
from motor.banco import Ejercicio

pytestmark = pytest.mark.skipif(terminal.encontrar_bash() is None or terminal.encontrar_git() is None,
                                reason="hace falta Git for Windows (git y bash)")


@pytest.fixture
def sandbox(tmp_path):
    return tmp_path / "sandbox"


def ej(**kw) -> Ejercicio:
    base = dict(id="tg-t", tipo="terminal_git", tema="terminal_git", concepto="c", nivel="basico", titulo="t",
                enunciado="e", origen="o", preparar="", solucion="", comprobaciones=[])
    base.update(kw)
    return Ejercicio(**base)


# ----------------------------------------------------------------- seguridad
@pytest.mark.parametrize("ident", ["../fuera", "a/b", "", "A", "x y", "..", "-rf"])
def test_identificadores_peligrosos_se_rechazan(ident, sandbox):
    with pytest.raises(terminal.ErrorTerminal):
        terminal.dir_base(ident, sandbox)


def test_no_se_borra_nada_fuera_del_sandbox(tmp_path):
    fuera = tmp_path / "importante"
    fuera.mkdir()
    (fuera / "a.txt").write_text("x")
    with pytest.raises(terminal.ErrorTerminal):
        terminal._borrar_arbol(fuera, tmp_path / "sandbox")
    with pytest.raises(terminal.ErrorTerminal):
        terminal._borrar_arbol(tmp_path / "sandbox", tmp_path / "sandbox")
    assert (fuera / "a.txt").exists()


@pytest.mark.parametrize("args, permitido", [
    (["status", "-sb"], True), (["log", "--oneline"], True), (["rev-parse", "HEAD"], True),
    (["branch", "--list"], True), (["branch", "--show-current"], True), (["tag", "-l"], True),
    (["remote", "-v"], True), (["remote"], True), (["config", "--get", "user.name"], True),
    (["stash", "list"], True), (["ls-files"], True),
    (["branch", "nueva"], False), (["branch", "-D", "x", "--list"], False), (["tag", "v1"], False),
    (["config", "user.name", "x"], False), (["commit", "-m", "x"], False), (["push"], False),
    (["reset", "--hard"], False), (["clean", "-fd"], False), (["checkout", "main"], False), ([], False),
    (["remote", "add", "o", "u"], False),
])
def test_solo_se_permiten_comandos_git_de_lectura(args, permitido):
    assert (terminal._git_permitido(args) is None) is permitido


def test_una_comprobacion_peligrosa_es_un_error_del_banco(sandbox):
    e = ej(comprobaciones=[{"git": "reset --hard", "igual": ""}])
    terminal.preparar(e, sandbox)
    r = terminal.comprobar(e, sandbox)
    assert r["estado"] == "error_banco"


def test_el_entorno_no_lleva_credenciales(monkeypatch, sandbox):
    monkeypatch.setenv("DB_PASSWORD", "secreto")
    monkeypatch.setenv("MYSQL_PWD", "secreto")
    env = terminal.entorno("tg-t", sandbox)
    assert "DB_PASSWORD" not in env and "MYSQL_PWD" not in env
    assert env["GIT_CEILING_DIRECTORIES"]


def test_git_no_sube_hasta_un_repo_de_fuera(tmp_path):
    """Si la carpeta de practica estuviera dentro de un repo real, Git no debe verlo."""
    externo = tmp_path / "externo"
    externo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=externo, check=True)
    sandbox = externo / "sandbox"
    e = ej(comprobaciones=[{"git": "rev-parse --show-toplevel", "contiene": "externo", "mensaje": "no es repo"}])
    terminal.preparar(e, sandbox)          # carpeta de trabajo SIN git init
    r = terminal.comprobar(e, sandbox)
    assert r["estado"] == "fallo"           # no ha encontrado el repo externo
    assert "iniciaste el repositorio" in r["mensajes"][0]


# ------------------------------------------------------------ preparar / resolver
GIT_BASE = dict(
    preparar="git init -q -b main\necho hola > notas.txt\ngit add .\ngit commit -q -m 'primer commit'",
    solucion="git checkout -q -b feature/x\nmkdir datos\ntouch datos/a.csv\ngit add .\ngit commit -q -m 'feat: datos'",
    comprobaciones=[
        {"git": "rev-parse --abbrev-ref HEAD", "igual": "feature/x", "mensaje": "Cambia de rama."},
        {"archivo": "datos", "carpeta": True, "mensaje": "Falta la carpeta."},
        {"git": "log --format=%s", "contiene": "feat: datos", "mensaje": "Haz un commit."},
        {"git": "status --porcelain", "igual": "", "mensaje": "Hay cambios sin commitear."},
    ],
)


def test_preparar_comprobar_resolver(sandbox):
    e = ej(**GIT_BASE)
    assert terminal.comprobar(e, sandbox)["estado"] == "sin_preparar"
    assert terminal.preparar(e, sandbox)["ok"]
    r = terminal.comprobar(e, sandbox)
    assert r["estado"] == "fallo"
    assert [c["ok"] for c in r["comprobaciones"]] == [False, False, False, True]
    assert "Cambia de rama" in r["mensajes"][0]
    ok, salida = terminal.resolver(e, sandbox)
    assert ok, salida
    assert terminal.comprobar(e, sandbox)["estado"] == "ok"


def test_reiniciar_borra_el_trabajo_anterior(sandbox):
    e = ej(**GIT_BASE)
    terminal.preparar(e, sandbox)
    terminal.resolver(e, sandbox)
    (terminal.dir_trabajo("tg-t", sandbox) / "basura.txt").write_text("x")
    assert terminal.preparar(e, sandbox)["ok"]
    assert not (terminal.dir_trabajo("tg-t", sandbox) / "basura.txt").exists()
    assert terminal.comprobar(e, sandbox)["estado"] == "fallo"


def test_un_script_de_preparacion_roto_da_un_error_claro(sandbox):
    e = ej(preparar="git commit -m 'no hay repo'")
    r = terminal.preparar(e, sandbox)
    assert r["ok"] is False and "Fallo al montar" in r["error"]


def test_remoto_local_para_push_y_pull(sandbox):
    e = ej(remoto=True,
           preparar="git init -q -b main\necho a > a.txt\ngit add .\ngit commit -q -m uno\ngit remote add origin ../remoto.git",
           solucion="git push -q -u origin main",
           comprobaciones=[{"git": "rev-parse origin/main", "regex": "^[0-9a-f]{40}$", "mensaje": "No has subido."},
                           {"git": "rev-parse --abbrev-ref main@{upstream}", "igual": "origin/main", "mensaje": "Falta -u."}])
    terminal.preparar(e, sandbox)
    assert terminal.comprobar(e, sandbox)["estado"] == "fallo"
    ok, salida = terminal.resolver(e, sandbox)
    assert ok, salida
    assert terminal.comprobar(e, sandbox)["estado"] == "ok"


# ---------------------------------------------------------- tipos de comprobacion
def test_comprobaciones_de_archivos(sandbox):
    e = ej(preparar="printf 'b 2\\na   1\\n' > t.txt\nmkdir carpeta",
           comprobaciones=[
               {"archivo": "t.txt", "contiene": "a   1"},
               {"archivo": "t.txt", "igual_normalizado": "b 2\na 1"},
               {"archivo": "t.txt", "lineas": 2},
               {"archivo": "t.txt", "regex": r"^a\s+1$"},
               {"archivo": "carpeta", "carpeta": True},
               {"archivo": "t.txt", "carpeta": True},
               {"archivo": "no_existe.txt", "existe": False},
               {"archivo": "t.txt", "existe": False},
               {"archivo": "t.txt", "no_contiene": "zzz"},
               {"archivo": "no_existe.txt", "contiene": "x"},
           ])
    terminal.preparar(e, sandbox)
    r = terminal.comprobar(e, sandbox)
    assert [c["ok"] for c in r["comprobaciones"]] == [True, True, True, True, True, False, True, False, True, False]


def test_una_comprobacion_no_puede_salirse_de_la_carpeta(sandbox):
    e = ej(comprobaciones=[{"archivo": "../../../etc/passwd", "existe": True}])
    terminal.preparar(e, sandbox)
    assert terminal.comprobar(e, sandbox)["estado"] == "error_banco"


def test_permitir_error_para_comandos_que_devuelven_1(sandbox):
    e = ej(preparar="git init -q -b main\necho x > a.txt", solucion="echo a.txt > .gitignore",
           comprobaciones=[{"git": "check-ignore a.txt", "igual": "a.txt", "permitir_error": True, "mensaje": "No se ignora."}])
    terminal.preparar(e, sandbox)
    assert terminal.comprobar(e, sandbox)["estado"] == "fallo"
    terminal.resolver(e, sandbox)
    assert terminal.comprobar(e, sandbox)["estado"] == "ok"


def test_el_estado_del_repo_se_puede_consultar_sin_modificarlo(sandbox):
    e = ej(**GIT_BASE)
    terminal.preparar(e, sandbox)
    antes = terminal.estado_repo(e, sandbox)
    assert "notas.txt" in antes and "primer commit" in antes and "## main" in antes
    assert terminal.estado_repo(e, sandbox) == antes
    solo = ej(id="tg-vacio")
    terminal.preparar(solo, sandbox)
    assert "no es un repositorio Git" in terminal.estado_repo(solo, sandbox)
    assert "todavía no existe" in terminal.estado_repo(ej(id="tg-otro"), sandbox)


def test_git_con_identidad_aislada_de_la_del_alumno(sandbox, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Otro")
    e = ej(preparar="git init -q -b main\ngit commit -q --allow-empty -m x")
    terminal.preparar(e, sandbox)
    codigo, salida = terminal.ejecutar_git(["log", "--format=%an"], terminal.dir_trabajo("tg-t", sandbox),
                                           terminal.entorno("tg-t", sandbox))
    assert salida.strip() == "Practicador"


def test_el_git_bash_del_alumno_conserva_su_configuracion_pero_queda_encerrado(sandbox):
    env = terminal.entorno("tg-t", sandbox, con_identidad=False)
    assert env["GIT_CEILING_DIRECTORIES"]
    for var in ("GIT_EDITOR", "GIT_MERGE_AUTOEDIT", "GIT_CONFIG_GLOBAL", "GIT_AUTHOR_NAME"):
        assert var not in env or env[var] == __import__("os").environ.get(var)
