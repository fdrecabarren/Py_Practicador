# Practicador

App local para practicar lo que se ve en el bootcamp de Data Analytics (Factoría F5), con tus propios datos de Kiva y Olist. Python + Streamlit, todo en tu ordenador, sin APIs de pago.

**¿Eres compañero/a del bootcamp?** Empieza por el [manual de instalación y uso](MANUAL.md).

**Estado:** Fases 1 y 2 hechas (Python básico, pandas, SQL, Excel/Power Query y Terminal/Git). La fase 3 (repaso espaciado, "Sesión de hoy") está por hacer.

## Cómo funciona

1. Eliges un ejercicio. Lees el enunciado y lo intentas tú.
2. **Ejecutar** (o **Revisar sin contar**) prueba tu trabajo sin que cuente. **Comprobar** lo corrige y cuenta como intento.
3. Si falla, ves por qué (o el error real de Python / MySQL) sin que se revele la respuesta.
4. Tienes 3 pistas: idea general, pista concreta y solución explicada. La solución solo se desbloquea después de un intento.
5. Un ejercicio está **aprendido** si lo resuelves sin ver la solución. Si la ves, vuelve más adelante y solo cuenta si lo resuelves otro día.
6. Cada nivel (básico, intermedio, junior) se supera con un 70 % de ejercicios aprendidos y requiere el anterior superado.

## Primera vez

Necesitas Windows y Python 3.13 (el mismo que usas en el curso).

1. Doble clic en **`instalar.bat`**. Crea el entorno `.venv`, instala las dependencias, crea tu `.env` y prepara los datasets.
2. Edita **`.env`** con tus credenciales de MySQL (para los ejercicios SQL). Mira abajo cómo crear un usuario de solo lectura.
3. Doble clic en **`practicar.bat`**. Se abre la app en el navegador (solo escucha en tu ordenador, `127.0.0.1`).

**Modo oscuro:** menú **⋮** de arriba a la derecha > **Dark** (o **System** para seguir el de Windows). El navegador lo recuerda. Si lo cambias con un ejercicio abierto, el editor de código se adapta al siguiente clic.

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

## Excel y Power Query

Necesitas **Excel de escritorio** (Power Query no existe en la versión web). Cada ejercicio funciona así:

1. Descargas un `.xlsx` de práctica (la app lo genera con tus datos de Kiva o Customer_Activity).
2. Lo resuelves en Excel y lo guardas (**Ctrl+G**; los valores calculados solo se guardan si Excel guarda el archivo).
3. Lo subes. La app lee los **valores** de las celdas (no compara el texto de tus fórmulas, salvo que el ejercicio pida usar cierta función o una referencia como `$F$1`) y te dice qué falta.

Las fórmulas se guardan en inglés dentro del archivo (`SUMIFS`, `IF`...), aunque tu Excel las muestre en español. En los ejercicios de Power Query se comprueba el **resultado** cargado en la hoja que pide el enunciado. La presencia de la consulta (y trozos de su código M) solo se avisa, nunca suspende: ese detalle está sin probar con un archivo guardado por tu Excel.

## Terminal y Git

Necesitas **Git for Windows** (incluye Git Bash). Cada ejercicio tiene su propia carpeta en `sandbox/<id>/trabajo` (ignorada por Git):

- **Preparar ejercicio** crea la carpeta con el punto de partida; **Reiniciar** la vuelve a crear desde cero.
- **Abrir Git Bash aquí** abre la terminal dentro de esa carpeta. Tú escribes los comandos.
- **Ver estado** muestra archivos, `git status` y el historial (solo lee). **Comprobar** corrige el estado final.

Seguridad: la app nunca toca tus repositorios reales. El Git de la carpeta de práctica no puede subir hasta el repositorio del propio proyecto (`GIT_CEILING_DIRECTORIES`), las comprobaciones solo ejecutan comandos de lectura de Git, y los remotos que piden algunos ejercicios son carpetas locales (`remoto.git`), sin cuentas ni contraseñas. Si usas **tu propia** terminal en lugar del botón, copia antes el `export GIT_CEILING_DIRECTORIES=...` que muestra la app.

## Datos

Los CSV de práctica **ya vienen incluidos** en `datos/` (procedencia y fuentes en [`datos/LEEME.md`](datos/LEEME.md)). No los modifiques: los ejercicios están calibrados con esas filas exactas.

`python scripts/preparar_datos.py` solo crea los que falten y deja los existentes como están. Para regenerarlos todos desde el material del curso (solo lo necesita quien mantiene el proyecto) usa `python scripts/preparar_datos.py --forzar`. Salen muestras pequeñas y siempre iguales (semilla fija) a partir del material del curso, que solo se lee:

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

`validar_banco.py` comprueba que no hay ejercicios rotos: la solución pasa sus tests, el código inicial **no** los pasa y la primera pista no contiene la solución. En Excel valida contra un libro "resuelto" sintético y en Terminal/Git ejecuta la solución con tu Git Bash real en una carpeta temporal. Sin credenciales de MySQL valida el SQL contra un mini-Olist sintético en SQLite; `sq-015` (`GROUP_CONCAT`) solo se puede validar con MySQL.

## Cómo añadir ejercicios

Los ejercicios son archivos YAML en `ejercicios/`, separados del código. Hay un ejercicio completo de cada tipo en `ejercicios/*.yaml` y todos los campos están explicados en [`CLAUDE.md`](CLAUDE.md).

La forma más cómoda: abre Claude Code en esta carpeta y pide **"añade ejercicios de la clase X"**. Seguirá la misma estructura y validará el banco. Si los editas a mano:

1. Copia un ejercicio parecido, cambia `id`, `concepto`, `nivel`, `enunciado`, `codigo_inicial`, `solucion`, `pistas` (3) y `explicacion`.
2. Ejecuta `python scripts/validar_banco.py`.
3. En la app, **Conexión y ajustes > Recargar banco**.

## Organización del código

```
app.py            navegación de Streamlit
paginas/          pantallas: inicio, practicar (+ vistas_fase2: paneles de Excel y Terminal), progreso, ajustes
motor/            lógica sin Streamlit: banco, comparador, ejecutor Python, SQL, Excel, Terminal/Git, niveles, progreso
ejercicios/       banco en YAML (un archivo por tema + preguntas tipo test)
scripts/          preparar_datos, validar_banco, probar_conexion, usuario_mysql.sql
tests/            pytest
datos/            CSV de muestra (incluidos en el repositorio, ver datos/LEEME.md)
docs/img/         capturas del manual
progreso/ sandbox/  generados en local (no se suben a Git)
```

Tu progreso vive en `progreso/progreso.db` (SQLite). Puedes borrarlo desde **Mi progreso > Borrar todo mi progreso**.
