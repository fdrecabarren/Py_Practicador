"""Prepara los datasets de practica en datos/ a partir del material del curso.

Uso (con el venv activo):
    python scripts/preparar_datos.py

Lee (solo lectura) de la carpeta del curso (por defecto E:\\Data_Analytic) y escribe
muestras pequenas y reproducibles en practicador/datos/. Siempre salen las mismas filas
(semilla fija), asi los ejercicios y sus soluciones no cambian entre ejecuciones.
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from motor.config import DIR_CURSO, DIR_DATOS  # noqa: E402

SEMILLA = 42
OLIST_OUT = DIR_CURSO / "Proyetos" / "Flujo_de_Datos_de_SQL_a_Python_tania_lena_eddy_franco" / "output"
KIVA_COMPLETO = DIR_CURSO / "Proyetos" / "Proyecto-2-Python-Ray-Franco" / "data" / "kiva_loans.csv"
KIVA_REDUCIDO = DIR_CURSO / "Clases" / "Excel" / "Practica" / "Ejecicio 1" / "kiva_loans.csv"
CUSTOMER = DIR_CURSO / "Clases" / "Excel" / "Practica" / "Customer_Activity.csv"


def _necesita(ruta: Path) -> bool:
    if not ruta.exists():
        print(f"  AVISO: no encuentro {ruta}. Me salto este dataset.")
        return False
    return True


def kiva() -> None:
    origen = KIVA_COMPLETO if KIVA_COMPLETO.exists() else KIVA_REDUCIDO
    if not _necesita(origen):
        return
    print(f"Kiva: leyendo {origen.name} ...")
    # keep_default_na=False: los textos como "NA" se conservan tal cual; solo los campos
    # vacios son nulos (asi la muestra es fiel al CSV original).
    df = pd.read_csv(origen, keep_default_na=False, na_values=[""])
    # 3000 filas al azar + todas las de Namibia (en el CSV su country_code viene vacio: son
    # justo las filas que borra un dropna(subset=["country_code"]) sin mirar antes)
    namibia = df[df["country"] == "Namibia"]
    resto = df.drop(namibia.index).sample(n=min(3000, len(df) - len(namibia)), random_state=SEMILLA)
    muestra = pd.concat([resto, namibia]).sort_index()
    # Se guarda sin cambiar nada: nulos, espacios y fechas como texto, tal como llegan en el curso
    muestra.to_csv(DIR_DATOS / "kiva_muestra.csv", index=False)
    print(f"  kiva_muestra.csv: {len(muestra)} filas ({len(namibia)} de Namibia)")


def olist() -> None:
    for nombre, destino, n in [
        ("ventas_detalle.csv", "olist_ventas.csv", 4000),
        ("df1_actividad_clientes.csv", "olist_pedidos.csv", 4000),
        ("df3_vendedores.csv", "olist_vendedores.csv", None),
    ]:
        origen = OLIST_OUT / nombre
        if not _necesita(origen):
            continue
        df = pd.read_csv(origen, encoding="utf-8-sig")
        if n and len(df) > n:
            df = df.sample(n=n, random_state=SEMILLA).sort_index()
        df.to_csv(DIR_DATOS / destino, index=False, encoding="utf-8")
        print(f"  {destino}: {len(df)} filas")


def customer() -> None:
    if _necesita(CUSTOMER):
        shutil.copyfile(CUSTOMER, DIR_DATOS / "customer_activity.csv")
        print("  customer_activity.csv: copiado tal cual (separador ';', cabecera ' amount ')")


def main() -> None:
    DIR_DATOS.mkdir(exist_ok=True)
    kiva()
    olist()
    customer()
    print(f"Listo. Datos en {DIR_DATOS}")


if __name__ == "__main__":
    main()
