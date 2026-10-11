"""Progreso del alumno en una base SQLite local (progreso/progreso.db).

Reglas:
- Un ejercicio esta APRENDIDO si lo has resuelto sin haber visto la solucion.
- Si ves la solucion, pasa a NO APRENDIDO. Para volver a contar tiene que resolverse
  correctamente en un dia posterior al que viste la solucion.
- La solucion solo se puede ver despues de al menos un intento.
- Cada dia con al menos un intento cuenta para la racha.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from . import config

ESQUEMA_V1 = """
CREATE TABLE intentos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ejercicio_id  TEXT NOT NULL,
    tema          TEXT NOT NULL,
    concepto      TEXT NOT NULL,
    nivel         TEXT NOT NULL,
    fecha         TEXT NOT NULL,
    dia           TEXT NOT NULL,
    correcto      INTEGER NOT NULL,
    pista_max     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_intentos_ej ON intentos(ejercicio_id);
CREATE INDEX idx_intentos_dia ON intentos(dia);

CREATE TABLE ejercicios_estado (
    ejercicio_id        TEXT PRIMARY KEY,
    tema                TEXT NOT NULL,
    concepto            TEXT NOT NULL,
    nivel               TEXT NOT NULL,
    aprendido           INTEGER NOT NULL DEFAULT 0,
    solucion_vista_dia  TEXT,
    primer_dia          TEXT,
    ultimo_dia          TEXT,
    intentos            INTEGER NOT NULL DEFAULT 0,
    aciertos            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE dias_practica (dia TEXT PRIMARY KEY);
"""


class Progreso:
    def __init__(self, ruta: Path | str | None = None, reloj: Callable[[], datetime] | None = None):
        self.ruta = Path(ruta or config.DB_PROGRESO)
        self.reloj = reloj or datetime.now
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self._migrar()

    # ---------------------------------------------------------------- infra
    def _migrar(self) -> None:
        version = self.con.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.con.executescript(ESQUEMA_V1)
            self.con.execute("PRAGMA user_version = 1")
        self.con.commit()

    def cerrar(self) -> None:
        self.con.close()

    def hoy(self) -> date:
        return self.reloj().date()

    # ------------------------------------------------------------- registro
    def registrar_intento(self, ej, correcto: bool, pista_max: int = 0) -> dict:
        """Guarda un intento. `ej` necesita .id .tema .concepto .nivel.
        Devuelve {'aprendido': bool, 'aviso': str | None}."""
        ahora, dia = self.reloj(), self.hoy().isoformat()
        self.con.execute(
            "INSERT INTO intentos(ejercicio_id, tema, concepto, nivel, fecha, dia, correcto, pista_max) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ej.id, ej.tema, ej.concepto, ej.nivel, ahora.isoformat(timespec="seconds"), dia, int(correcto), pista_max),
        )
        self.con.execute("INSERT OR IGNORE INTO dias_practica(dia) VALUES (?)", (dia,))
        fila = self.con.execute("SELECT * FROM ejercicios_estado WHERE ejercicio_id=?", (ej.id,)).fetchone()
        if fila is None:
            self.con.execute(
                "INSERT INTO ejercicios_estado(ejercicio_id, tema, concepto, nivel, primer_dia) VALUES (?,?,?,?,?)",
                (ej.id, ej.tema, ej.concepto, ej.nivel, dia),
            )
            fila = self.con.execute("SELECT * FROM ejercicios_estado WHERE ejercicio_id=?", (ej.id,)).fetchone()

        aprendido, aviso = bool(fila["aprendido"]), None
        if correcto:
            vista = fila["solucion_vista_dia"]
            if vista is not None and vista >= dia:
                aviso = ("Lo has resuelto, pero después de ver la solución. "
                         "Vuelve a intentarlo mañana sin mirarla para que cuente como aprendido.")
            else:
                aprendido = True
        self.con.execute(
            "UPDATE ejercicios_estado SET intentos=intentos+1, aciertos=aciertos+?, aprendido=?, ultimo_dia=? "
            "WHERE ejercicio_id=?",
            (int(correcto), int(aprendido), dia, ej.id),
        )
        self.con.commit()
        return {"aprendido": aprendido, "aviso": aviso}

    def registrar_solucion_vista(self, ej) -> None:
        """Ver la solucion deja el ejercicio como NO aprendido."""
        dia = self.hoy().isoformat()
        self.con.execute(
            "INSERT OR IGNORE INTO ejercicios_estado(ejercicio_id, tema, concepto, nivel, primer_dia) VALUES (?,?,?,?,?)",
            (ej.id, ej.tema, ej.concepto, ej.nivel, dia),
        )
        self.con.execute(
            "UPDATE ejercicios_estado SET aprendido=0, solucion_vista_dia=?, ultimo_dia=? WHERE ejercicio_id=?",
            (dia, dia, ej.id),
        )
        self.con.commit()

    # ------------------------------------------------------------ consultas
    def num_intentos(self, ejercicio_id: str) -> int:
        return self.con.execute(
            "SELECT COUNT(*) FROM intentos WHERE ejercicio_id=?", (ejercicio_id,)
        ).fetchone()[0]

    def puede_ver_solucion(self, ejercicio_id: str) -> bool:
        return self.num_intentos(ejercicio_id) >= 1

    def estado_ejercicio(self, ejercicio_id: str) -> dict | None:
        fila = self.con.execute("SELECT * FROM ejercicios_estado WHERE ejercicio_id=?", (ejercicio_id,)).fetchone()
        return dict(fila) if fila else None

    def aprendidos(self) -> set[str]:
        return {r[0] for r in self.con.execute("SELECT ejercicio_id FROM ejercicios_estado WHERE aprendido=1")}

    def no_aprendidos(self) -> list[str]:
        """Ejercicios cuya solucion se vio y aun no se han vuelto a resolver."""
        return [r[0] for r in self.con.execute(
            "SELECT ejercicio_id FROM ejercicios_estado WHERE aprendido=0 AND solucion_vista_dia IS NOT NULL"
        )]

    def ejercicios_tocados(self) -> set[str]:
        return {r[0] for r in self.con.execute("SELECT ejercicio_id FROM ejercicios_estado")}

    def stats_por_concepto(self) -> list[dict]:
        filas = self.con.execute(
            "SELECT tema, concepto, COUNT(*) AS intentos, SUM(correcto) AS aciertos "
            "FROM intentos GROUP BY tema, concepto ORDER BY tema, concepto"
        ).fetchall()
        res = []
        for f in filas:
            aprendidos = self.con.execute(
                "SELECT COUNT(*) FROM ejercicios_estado WHERE tema=? AND concepto=? AND aprendido=1",
                (f["tema"], f["concepto"]),
            ).fetchone()[0]
            res.append({**dict(f), "aprendidos": aprendidos})
        return res

    def ultimo_tema(self) -> str | None:
        fila = self.con.execute("SELECT tema FROM intentos ORDER BY id DESC LIMIT 1").fetchone()
        return fila[0] if fila else None

    def intentos_de_hoy(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM intentos WHERE dia=?", (self.hoy().isoformat(),)).fetchone()[0]

    def dias_practicados(self) -> list[date]:
        return sorted(date.fromisoformat(r[0]) for r in self.con.execute("SELECT dia FROM dias_practica"))

    def racha(self) -> dict:
        """{'actual': dias seguidos hasta hoy (o ayer), 'mejor': mejor racha, 'total': dias practicados}"""
        dias = set(self.dias_practicados())
        if not dias:
            return {"actual": 0, "mejor": 0, "total": 0, "hoy_practicado": False}
        hoy = self.hoy()
        cursor = hoy if hoy in dias else hoy - timedelta(days=1)
        actual = 0
        while cursor in dias:
            actual += 1
            cursor -= timedelta(days=1)
        mejor = racha_actual = 0
        previo = None
        for d in sorted(dias):
            racha_actual = racha_actual + 1 if previo and d - previo == timedelta(days=1) else 1
            mejor = max(mejor, racha_actual)
            previo = d
        return {"actual": actual, "mejor": mejor, "total": len(dias), "hoy_practicado": hoy in dias}

    def reiniciar(self) -> None:
        """Borra TODO el progreso (la app pide confirmacion antes)."""
        for tabla in ("intentos", "ejercicios_estado", "dias_practica"):
            self.con.execute(f"DELETE FROM {tabla}")
        self.con.commit()
