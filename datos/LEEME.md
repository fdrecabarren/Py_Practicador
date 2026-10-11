# Datos de práctica

Muestras pequeñas y siempre iguales (semilla 42) que usan los ejercicios. **No modifiques estos archivos: los ejercicios están calibrados con estas filas exactas.**

| Archivo | Origen | Filas |
|---|---|---|
| `kiva_muestra.csv` | Dataset de Kiva "Data Science for Good: Kiva Crowdfunding" (Kaggle, `kiva_loans.csv`) | 3.000 al azar + las 8 de Namibia |
| `olist_ventas.csv` | "Brazilian E-Commerce Public Dataset by Olist" (Kaggle), tabla `ventas_detalle` del proyecto de clase SQL a Python | 4.000 |
| `olist_pedidos.csv` | Igual, tabla `df1_actividad_clientes` del mismo proyecto | 4.000 |
| `olist_vendedores.csv` | Igual, tabla `df3_vendedores` del mismo proyecto | completa |
| `customer_activity.csv` | Material de la clase de Excel de Factoría F5 (datos ficticios de la base de ejemplo Sakila de MySQL) | completa |

Fuentes:

- Olist: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
- Kiva: <https://www.kaggle.com/competitions/data-science-for-good-kiva-crowdfunding>

Las licencias de uso de Kiva y Olist las fija cada fuente en su página de Kaggle; consúltalas allí antes de reutilizar los datos fuera de esta práctica.

## Regenerar los archivos

Solo si tienes el material original del curso (carpeta `Proyetos/` y `Clases/`):

```bash
python scripts/preparar_datos.py --forzar
```

Sin `--forzar`, el script no toca los archivos que ya existen.
