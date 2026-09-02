# Dashboard de siniestralidad vial (CONASET)

## Propósito

Dashboard de siniestros de tránsito en Chile a partir de los datos abiertos de CONASET, con lectura
territorial por comuna, región y punto.

## Estado

activo

## Entradas y salidas

Contrato completo en [`SALIDAS.md`](SALIDAS.md).

**QUÉ PRODUCE**

1. **El dashboard** (`index.html` + `data_bundle.js`) — el producto publicado.
2. **La base canónica del dashboard** (`data/parquet/siniestros_2020_2025.parquet`, 436.521 siniestros
   2020–2025, urbano+rural, todos georreferenciados) — la que alimenta el tablero hoy. La antigua
   `siniestros_consolidado.parquet` (375.489, 2020–2024) quedó **superada** por ésta.
3. **La base a nivel persona** (`data/parquet/personas.parquet`, 770.414 personas 2020–2024, con edad,
   sexo, rol y tipo de usuario) — alimenta la pestaña "Personas accidentadas".
4. **El riesgo hexagonal** (`data/riesgo/<cod_region>.json`, 6.275 hexágonos H3 res-8, tasa
   siniestros÷población Censo 2024) — el modo "Riesgo (hex)" del análisis espacial.
5. **Cartografía lista para unir** (`data/parquet/cartografia/comunas.parquet` 345,
   `regiones.parquet` 16).

**QUÉ CONSUME.** Datos abiertos de CONASET: la base 2020–2025 y la de personas se bajan de sus
FeatureServer del portal ArcGIS (`descargar_base_2025.py`, `descargar_personas.py`); las capas
temáticas históricas con `descargar_conaset.py`. Cartografía del Censo. La población por manzana para
el riesgo sale del **Censo 2024** (`censo2024_manzana_entidad.parquet`, en solo lectura desde otro
proyecto — ver Aprendizajes).

**Cifras de control:** Chile, 16 regiones · base **2020–2025** (Base_SINIESTROS_2020_2025 de CONASET) ·
**436.521 siniestros** · 770.414 personas · llave `cut_com` con join contra la cartografía comunal.

## Datos canónicos

- `data\parquet\siniestros_2020_2025.parquet` — **la base del dashboard hoy** (436.521, 2020–2025,
  urbano+rural, con banderas de modo Atropello/Bicicleta/Motociclet y `CAUSA_NUEV`). Usar ésta.
- `data\parquet\personas.parquet` — 770.414 personas (edad, sexo, rol, tipo de usuario CONASET).
- `data\parquet\siniestros_consolidado.parquet` + `data\accidentes.duckdb` — dedup 2020–2024 (375.489),
  **legado**: sigue en disco pero el dashboard ya no lo usa. Para análisis nuevos, preferir la 2020–2025.
- `data\parquet\cartografia\comunas.parquet` (345) y `regiones.parquet` (16).

## Aprendizajes

- **La base cambió (sep 2026):** el dashboard usa `siniestros_2020_2025.parquet` (Base_SINIESTROS_2020_2025
  de CONASET, 436.521), no el viejo consolidado stitcheado. El consolidado sigue en disco como legado.
- **DOBLE CONTEO en `siniestros_individuales`** (base vieja): cada año 2020–2024 aparece **dos veces** —
  nacional solo urbano, regional urbano+rural. Vale para esa capa; la 2020–2025 ya viene deduplicada.
- **`atropellos`, `motos`, `bicis`, `urbanos`, `en_ruta` son SUBCONJUNTOS**, no categorías
  independientes. Sumarlos con la tabla principal duplica.
- **`cut_com` viene en float, int o str según la capa.** Castear antes de unir, o el join devuelve
  cero filas sin avisar.
- **Paginar los FeatureServer de CONASET al `maxRecordCount` exacto** (suele ser 1000/2000): un paso
  mayor **salta registros en silencio** (así se bajó media base de personas la primera vez).
- **deck.gl: `H3HexagonLayer` NO renderiza** en el navegador acá (los contornos sí). Para hexágonos,
  usar `deck.PolygonLayer`/`GeoJsonLayer` con las fronteras ya calculadas (`h3.cell_to_boundary`).
- **Verificar el mapa con el pane EN PRIMER PLANO**: deck.gl/Chart.js/Leaflet usan rAF, que se suspende
  cuando el pane está oculto (`document.hidden`) → el canvas no compone y el screenshot sale en blanco.
- **Puntos y red vial NO se embeben**: van por región en `data/puntos/<cod>.json`, `data/redvial/<cod>.json`
  y `data/riesgo/<cod>.json`, con lazy-load (`ensureScope`). El bundle liviano evita el freeze de parseo.

## Cómo se ejecuta

```bash
# Pipeline actual (base 2020-2025 + personas + espacial)
python scripts/descargar_base_2025.py    # baja Base_SINIESTROS_2020_2025 (FeatureServer, paginado)
python scripts/convertir_base_2025.py    # -> data/parquet/siniestros_2020_2025.parquet
python scripts/descargar_personas.py     # baja Base_de_persona_vehiculo_4 (paso = maxRecordCount)
python scripts/convertir_personas.py     # -> data/parquet/personas.parquet
python scripts/segmentar_red_vial.py     # accidentes -> tramos de Red Vial Nacional (linear referencing)
python scripts/riesgo_hexagonal.py       # -> data/riesgo/<cod>.json (riesgo H3 x poblacion Censo 2024)
python procesar_accidentes.py            # -> data_bundle.js + data/puntos|redvial/<cod>.json
```
