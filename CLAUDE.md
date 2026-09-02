# Dashboard de siniestralidad vial (CONASET)

## Propósito

Dashboard de siniestros de tránsito en Chile a partir de los datos abiertos de CONASET, con lectura
territorial por comuna, región y punto.

## Estado

activo

<!-- Propuesto por Claude desde la evidencia (última actividad 2026-07-30). CONFIRMAR. -->

## Entradas y salidas

Contrato completo en [`SALIDAS.md`](SALIDAS.md).

**QUÉ PRODUCE**

1. **El dashboard** (`index.html` + `data_bundle.js`) — el producto publicado.
2. **La base consolidada y deduplicada** (`data/parquet/siniestros_consolidado.parquet`, 375.489
   siniestros) más su versión consultable (`data/accidentes.duckdb`) — reutilizable por otros
   análisis territoriales.
3. **Cartografía lista para unir** (`data/parquet/cartografia/comunas.parquet` 345,
   `regiones.parquet` 16).

**QUÉ CONSUME.** Datos abiertos de CONASET (descargados con `descargar_conaset.py`) y cartografía
del Censo.

**Cifras de control:** Chile, 16 regiones · base 2014–2024, dashboard 2020–2024 · 375.489 siniestros
consolidados · llave `cut_com` con join 100 % contra la cartografía comunal.

## Datos canónicos

- `C:\Users\Rodrigo\Análisis RMG\dashboard accidentes\data\parquet\siniestros_consolidado.parquet`
  — **usar esta, ya está deduplicada** (375.489 filas).
- `C:\Users\Rodrigo\Análisis RMG\dashboard accidentes\data\accidentes.duckdb` — la misma base,
  consultable.
- `C:\Users\Rodrigo\Análisis RMG\dashboard accidentes\data\parquet\cartografia\comunas.parquet`
  (345) y `regiones.parquet` (16).

## Aprendizajes

- **DOBLE CONTEO en `siniestros_individuales`:** cada año entre 2020 y 2024 aparece **dos veces** —
  el nivel nacional trae solo urbano y el regional trae urbano + rural. Síntoma: los totales salen
  ~2× de lo esperado. Qué hacer: **usar siempre `siniestros_consolidado`**, que ya está deduplicada.
- **`atropellos`, `motos`, `bicis`, `urbanos`, `en_ruta` son SUBCONJUNTOS**, no categorías
  independientes. Sumarlos con la tabla principal duplica.
- **Usar las columnas canónicas** (`region_norm`, `tipo_final`, `causa_final`), no las crudas `o_*`.
- **`cut_com` viene en float, int o str según la capa.** Castear antes de unir, o el join devuelve
  cero filas sin avisar.

## Cómo se ejecuta

```bash
python descargar_conaset.py          # baja los datos abiertos
python scripts/convertir_parquet.py  # TXT/CSV -> parquet
python scripts/consolidar.py         # deduplica -> siniestros_consolidado.parquet
python scripts/crear_duckdb.py       # -> accidentes.duckdb
python procesar_accidentes.py        # -> data_bundle.js del dashboard
```
