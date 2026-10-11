# Practicador: guía para Claude

App local (Python + Streamlit) para que Franco practique lo que ve en el bootcamp de Data Analytics (Factoría F5). **Es una herramienta de aprendizaje: nunca des la solución de un ejercicio directamente al alumno** (ni en el chat, ni en las pistas 1 y 2). La solución solo vive en el YAML y en la pista 3.

Cuando el alumno diga "añade ejercicios de la clase X", sigue la sección **Cómo añadir ejercicios**.

## Reglas del proyecto

- Interfaz y contenido en español, con tildes. Sin emojis ni guiones largos en el texto de los ejercicios.
- Todo local y gratis. Sin APIs de pago.
- Credenciales siempre en `.env` (ignorado por Git). Nunca leas, imprimas ni copies `.env` ni el `.env` de otros proyectos del curso.
- Nunca modifiques el material del curso en `E:\Data_Analytic` (Clases, Pildoras, Proyetos, SQL) ni sus repos Git. Solo lectura.
- Los datasets de `datos/` y el progreso de `progreso/` no se suben a Git (`.gitignore`).
- Antes de dar por bueno un cambio: `python scripts/validar_banco.py` y `python -m pytest -q`.

## Estructura

```
app.py                     entrada de Streamlit (navegación)
paginas/                   inicio, practicar, progreso, ajustes (+ comun.py con cache y editor)
motor/
  config.py                rutas, .env, umbral 70 %, niveles
  banco.py                 carga y valida los YAML (ErrorBanco con todos los problemas)
  comparar.py              compara VALORES (DataFrame, Series, listas, dict, escalares)
  harness.py               se ejecuta en un proceso aparte: ejecuta el código y corrige
  ejecutor_python.py       lanza harness.py con timeout en una carpeta temporal
  sql.py                   conexión MySQL (.env), validador de solo lectura, corrección
  fixture_olist.py         mini-Olist sintético en SQLite (solo tests y validación)
  niveles.py               regla del 70 %, bloqueo de niveles, siguiente ejercicio
  progreso.py              SQLite: intentos, ejercicios aprendidos, racha
ejercicios/                _temas.yaml + un YAML por tema (+ preguntas_test.yaml)
scripts/                   preparar_datos.py, validar_banco.py, probar_conexion.py, usuario_mysql.sql
tests/                     pytest del motor, del banco y de la interfaz (AppTest)
datos/ progreso/ sandbox/  generados en local, ignorados por Git
```

## Reglas de aprendizaje (ya implementadas)

- Un ejercicio está **aprendido** si se resuelve sin haber visto la solución.
- Ver la solución (pista 3) lo deja como **no aprendido**; solo vuelve a contar si se resuelve en un **día posterior**.
- La solución solo se puede ver tras **al menos un intento** (botón Comprobar; Ejecutar no cuenta).
- Un nivel (basico, intermedio, junior) de un tema se supera con **70 % o más** de sus ejercicios aprendidos y solo si el anterior está superado. Las preguntas `tipo: test` no cuentan para los niveles.

## Formato de un ejercicio

Cada archivo `ejercicios/<nombre>.yaml` es una **lista** de ejercicios. Los temas se declaran en `ejercicios/_temas.yaml` (`id`, `nombre`, `descripcion`, `fase`, `orden`). Un `tema` de un ejercicio debe existir ahí.

### Campos comunes (obligatorios salvo indicación)

| Campo | Contenido |
|---|---|
| `id` | Único en todo el banco. Prefijos: `pb-` python_basico, `pd-` pandas, `sq-` sql, `pq-` preguntas test. Siguiente número libre. |
| `tipo` | `python`, `sql` o `test` (Fase 2: `excel`, `terminal_git`). |
| `tema` | Id de un tema de `_temas.yaml`. |
| `concepto` | Concepto concreto y corto (`fillna`, `LEFT JOIN con IS NULL`). Las estadísticas y el repaso espaciado agrupan por este texto: **reutiliza exactamente los conceptos ya existentes** cuando sea el mismo. |
| `nivel` | `basico`, `intermedio` o `junior`. |
| `titulo` | Corto, como lo verá el alumno. |
| `enunciado` | Markdown. Debe decir exactamente qué dejar en `resultado` / qué columnas devolver y en qué orden. |
| `origen` | Archivo o clase de la que sale (ruta relativa a `E:\Data_Analytic` y, si procede, página/celda). Si el concepto aún no se ha visto en clase, dilo ("HAVING aún no se ha visto en clase"). |
| `explicacion` | Markdown. Por qué funciona, error típico y conexión con lo que ya conoce (Excel, Power Query, pandas, SQL). |
| `pistas` | Exactamente 3 textos: 1) idea general, 2) pista concreta (nombre de la función o cláusula, sin la solución completa), 3) solución explicada en palabras. La solución en código sale de `solucion`. |
| `codigo_inicial` | Qué ve el alumno en el editor. Mejor un código que **falle de forma instructiva** (error real) o que dé un resultado incorrecto, que un editor vacío. No debe pasar los tests. |
| `solucion` | Solución de referencia (código Python o consulta SQL). Obligatoria en `python` y `sql`. |

Campos opcionales: `datos` (lista de archivos de `datos/`, Python), `comparar` (opciones del comparador), `timeout` (segundos), `nota_dialecto` (texto sobre diferencias MySQL/SQLite), `solo_mysql: true` (el validador lo salta en SQLite).

### `tipo: python`

El código del alumno corre en un proceso aparte, en una carpeta temporal que solo contiene los archivos de `datos`. Los tests (`tests`, lista) pueden ser:

```yaml
tests:
  - tipo: resultado            # compara la variable `resultado` con la que deja `solucion`
  - tipo: funcion              # llama a una función del alumno con casos literales
    nombre: clasificar
    casos:
      - {args: [525], esperado: "Bajo"}
      - {args: ["5 degress"], esperado: null}
  - tipo: salida               # da `entrada` por input() y compara lo impreso
    entrada: "40\n10.5\n"
    esperado: "Pagar: 420.0"   # se comparan palabras y números, no el texto exacto
```

Si no pones `tests`, se usa `[{tipo: resultado}]`. `resultado` puede ser escalar, lista, tupla, set, dict, Series o DataFrame.

Opciones de `comparar` (también se pueden poner dentro de un test `resultado`):

| Opción | Por defecto | Uso |
|---|---|---|
| `ignorar_orden_filas` | `true` | `false` si el ejercicio pide ordenar. |
| `ignorar_orden_columnas` | `true` | |
| `ignorar_indice` | DataFrame `true`, Series `false` | `true` si el índice no importa (`reset_index`). |
| `ignorar_orden_lista` | `false` | `true` si el orden de una lista no importa. |
| `tolerancia` | `1e-6` | Para floats. |

Reglas para escribir ejercicios Python:
- Pide el resultado en la variable `resultado` (o una función / una salida por pantalla).
- Los mensajes de la comparación nunca revelan los valores esperados de `resultado`; no hace falta que tú lo hagas, pero no pongas el valor final en las pistas 1 y 2.
- Evita resultados no deterministas (orden de un `set`, empates en `head(n)` de `value_counts`). Si hay empates, ordena por una segunda clave o compara solo valores.
- Los datasets se leen por nombre de archivo relativo (`pd.read_csv("kiva_muestra.csv")`).

### `tipo: sql`

La respuesta correcta es lo que devuelve `solucion` ejecutada sobre el MySQL local del alumno (base `olist`). El alumno solo puede ejecutar SELECT / WITH.

```yaml
comparar:
  ordenado: true   # el ejercicio exige ORDER BY: se compara el orden de filas
  alias: true      # los nombres de columna deben coincidir (el enunciado pide AS)
```

Reglas para escribir ejercicios SQL:
- Usa solo tablas y columnas que ya aparecen en el proyecto del alumno: `orders`, `customers`, `order_items`, `order_payments`, `order_reviews`, `products`, `sellers`, `geolocation`, `categoria_traduccion`. Columnas confirmadas en `Proyetos/Flujo_de_Datos_.../queries/*.sql`.
- Indica en el enunciado el número y el orden de las columnas.
- Con `ordenado: true`, añade siempre un desempate único (`ORDER BY x DESC, id`).
- Evita resultados de más de 20.000 filas (agrega o filtra).
- Para sintaxis solo de MySQL (`GROUP_CONCAT ... SEPARATOR`, etc.) pon `solo_mysql: true` y `nota_dialecto`. `YEAR`, `MONTH`, `DAY`, `DATEDIFF` y `DATE_FORMAT` básico están emuladas en el mini-Olist de pruebas.

### `tipo: test` (pregunta rápida)

```yaml
- id: pq-016
  tipo: test
  tema: pandas
  concepto: isnull().sum()
  nivel: basico
  titulo: ...
  origen: ...
  enunciado: |
    Pregunta (Markdown, puede llevar código).
  opciones: ["A", "B", "C", "D"]   # 2 o más, sin repetidas
  correcta: 1                       # índice desde 0
  explicacion: |
    Por qué es correcta y por qué fallan las otras.
```
No llevan `pistas`, `codigo_inicial` ni `solucion`. No cuentan para superar niveles.

## Cómo añadir ejercicios ("añade ejercicios de la clase X")

1. **Lee el material real** de esa clase en `E:\Data_Analytic` (PDF, notebook, .sql, .py, xlsx). No inventes contenido que no se haya visto; si añades algo que va más allá, márcalo en `origen`.
2. Elige conceptos que la clase cubre y reparte niveles con realismo: el alumno parte casi de cero (Python básico = print/input/operadores; intermedio = if/for/listas/funciones sencillas; junior = lo que combina varios conceptos).
3. Basa los ejercicios en **sus datasets**: Kiva (`kiva_muestra.csv`), Olist (`olist_*.csv` o la base MySQL) y Customer_Activity. Prefiere casos reales que ya le dieron problemas (nulos de Namibia, importes x10, `31/02`, el JOIN que multiplica filas).
4. Añade los ejercicios al YAML del tema (ids nuevos) o crea otro `ejercicios/<tema>_<clase>.yaml`. Si el tema es nuevo, decláralo en `_temas.yaml`.
5. Si necesitas un dataset nuevo, añádelo a `scripts/preparar_datos.py` (muestra pequeña, semilla fija, solo lectura del curso) y lístalo en `datos:`.
6. Valida: `python scripts/validar_banco.py` (cada solución pasa sus tests, el código inicial no, las pistas 1 no filtran la solución) y `python -m pytest -q`.
7. Si algún SQL solo se puede probar con MySQL real, avísalo al alumno: `python scripts/validar_banco.py --sql mysql`.
8. Haz commit (`git add ejercicios scripts tests`) con un mensaje claro.

## Pendiente por fases

- Fase 2: temas `excel_pq` (genera `.xlsx` con instrucciones y lee valores de celdas con openpyxl; las fórmulas se guardan en inglés y los valores calculados solo existen si Excel guardó el archivo) y `terminal_git` (sandbox dentro del proyecto con su propio repo; botón Comprobar; nunca tocar repos reales).
- Fase 3: repaso espaciado (1, 3 y 7 días por concepto fallado), panel de progreso ampliado y "Sesión de hoy" (unos 20 minutos).
