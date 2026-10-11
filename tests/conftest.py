"""Los tests nunca tocan el progreso real: usan una base temporal."""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["PRACTICADOR_DB"] = str(Path(tempfile.mkdtemp(prefix="practicador_test_")) / "progreso.db")
# Sin credenciales de MySQL: la interfaz debe degradarse con un aviso claro.
os.environ["DB_USER"] = ""
os.environ["DB_PASSWORD"] = ""
