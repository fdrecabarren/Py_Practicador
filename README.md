# Practicador

App local para practicar lo que se ve en el bootcamp de Data Analytics (Factoría F5), con tus propios datos de Kiva y Olist. Python + Streamlit, todo en tu ordenador, sin APIs de pago.

**Estado:** Fase 1 (Python básico, pandas y SQL). Las fases 2 (Excel/Power Query, Terminal y Git) y 3 (repaso espaciado, "Sesión de hoy") están por hacer.

## Cómo funciona

1. Eliges un ejercicio. Lees el enunciado y lo intentas tú.
2. **Ejecutar** prueba tu código sin que cuente. **Comprobar** lo corrige y cuenta como intento.
3. Si falla, ves por qué (o el error real de Python / MySQL) sin que se revele la respuesta.
4. Tienes 3 pistas: idea general, pista concreta y solución explicada. La solución solo se desbloquea después de un intento.
5. Un ejercicio está **aprendido** si lo resuelves sin ver la solución. Si la ves, vuelve más adelante y solo cuenta si lo resuelves otro día.
6. Cada nivel (básico, intermedio, junior) se supera con un 70 % de ejercicios aprendidos y requiere el anterior superado.

## Primera vez

Necesitas Windows y Python 3.13 (el mismo que usas en el curso).

1. Doble clic en **`instalar.bat`**. Crea el entorno `.venv`, instala las dependencias, crea tu `.env` y prepara los datasets.
2. Edita **`.env`** con tus credenciales de MySQL (para los ejercicios SQL). Mira abajo cómo crear un usuario de solo lectura.
3. Doble clic en **`practicar.bat`**. Se abre la app en el navegador (solo escucha en tu ordenador, `127.0.0.1`).

Si prefieres la terminal (Git Bash):

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
python scripts/preparar_datos.py
streamlit run app.py
```

## Conectar MySQL (ejercicios SQL)

Las credenciales van **solo** en `.env` (ignorado por Git). Usa las mismas variables que tu proyecto de Olist:

```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=olist
DB_USER=practicador
DB_PASSWORD=tu_contraseña
```

Recomendado: un usuario que solo pueda leer. Abre `scripts/usuario_mysql.sql` en MySQL Workbench, cambia la contraseña y ejecútalo con tu usuario `root`. Después comprueba la conexión:

```bash
python scripts/probar_conexion.py
```

La app solo acepta consultas `SELECT` / `WITH`, abre la sesión en modo solo lectura y limita el tiempo de ejecución.

## Datos

`python scripts/preparar_datos.py` crea en `datos/` muestras pequeñas y siempre iguales (semilla fija) a partir del material del curso, que solo se lee:

| Archivo | Origen |
|---|---|
| `kiva_muestra.csv` | `Proyetos/Proyecto-2-Python-Ray-Franco/data/kiva_loans.csv` (3.000 filas al azar + las 8 de Namibia) |
| `olist_vendedores.csv`, `olist_ventas.csv`, `olist_pedidos.csv` | `Proyetos/Flujo_de_Datos_.../output/*.csv` |
| `customer_activity.csv` | `Clases/Excel/Practica/Customer_Activity.csv` |

Si tu carpeta del curso no está en `E:\Data_Analytic`, define `CURSO_DIR` en `.env`.

## Tests y validación

```bash
python -m pytest -q                      # motor, banco e interfaz
python scripts/validar_banco.py          # cada solución de referencia pasa sus tests
python scripts/validar_banco.py --sql mysql   # SQL contra tu MySQL real
```

`validar_banco.py` comprueba que no hay ejercicios rotos: la solución pasa sus tests, el código inicial **no** los pasa y la primera pista no contiene la solución. Sin credenciales de MySQL valida el SQL contra un mini-Olist sintético en SQLite; `sq-015` (`GROUP_CONCAT`) solo se puede validar con MySQL.

## Cómo añadir ejercicios

Los ejercicios son archivos YAML en `ejercicios/`, separados del código. Hay un ejercicio completo de cada tipo en `ejercicios/*.yaml` y todos los campos están explicados en [`CLAUDE.md`](CLAUDE.md).

La forma más cómoda: abre Claude Code en esta carpeta y pide **"añade ejercicios de la clase X"**. Seguirá la misma estructura y validará el banco. Si los editas a mano:

1. Copia un ejercicio parecido, cambia `id`, `concepto`, `nivel`, `enunciado`, `codigo_inicial`, `solucion`, `pistas` (3) y `explicacion`.
2. Ejecuta `python scripts/validar_banco.py`.
3. En la app, **Conexión y ajustes > Recargar banco**.

## Organización del código

```
app.py            navegación de Streamlit
paginas/          pantallas: inicio, practicar, progreso, ajustes
motor/            lógica sin Streamlit: banco, comparador, ejecutor Python, SQL, niveles, progreso
ejercicios/       banco en YAML (un archivo por tema + preguntas tipo test)
scripts/          preparar_datos, validar_banco, probar_conexion, usuario_mysql.sql
tests/            pytest
datos/ progreso/  generados en local (no se suben a Git)
```

Tu progreso vive en `progreso/progreso.db` (SQLite). Puedes borrarlo desde **Mi progreso > Borrar todo mi progreso**.
