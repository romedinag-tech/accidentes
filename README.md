# Dashboard de Accidentes de Tránsito — Chile

Dashboard web de **siniestros de tránsito en Chile** (CONASET), 2020–2024, y toda la base de datos
georreferenciada que lo alimenta.

## El dashboard

`index.html` — dashboard estático autocontenido (Leaflet + Chart.js, sin build, funciona offline con
los datos embebidos en `data_bundle.js`). Para verlo: abrir `index.html` en el navegador.

Incluye: KPIs (siniestros, fallecidos, lesionados, tasa por 100 mil hab.), **mapa comunal** (coropleta
por siniestros / fallecidos / tasa / graves), evolución anual, y desgloses por región, tipo, causa,
mes, hora y día de la semana. Filtros: año, región, **comuna**, tipo de siniestro y zona (urbana/rural).

Dos vistas de análisis focalizado:
- **Tendencia por ciudad segmentada por tipo.** Al elegir una comuna (clic en el mapa o selector),
  todo el tablero se contextualiza a esa ciudad y la *evolución anual* se muestra **apilada por tipo de
  siniestro** → se ve si la siniestralidad es estable o evoluciona, y qué tipos la componen.
- **Zonificación / zonas de concentración ("zonas oscuras").** El mapa tiene modo **Concentración
  (calor)**: agrega los siniestros en una grilla (~330 m) y dibuja un mapa de calor que revela los
  sectores con mayor densidad de siniestros dentro de la ciudad. Se activa automáticamente al
  seleccionar una comuna (o manualmente con el toggle del mapa). Datos en `data.gridHot`.

- **Alcance:** 2020–2024 (años con cobertura nacional completa = 16 regiones). ~290 mil siniestros
  deduplicados. Georreferenciación principalmente urbana; cobertura rural parcial (mayor 2020–2022).
- **Regenerar el dashboard** (desde los shapefiles):
  ```bash
  python scripts/convertir_parquet.py   # shapefiles -> GeoParquet
  python scripts/consolidar.py          # dedup por id_accidente -> siniestros_consolidado.parquet
  python procesar_accidentes.py         # -> data_bundle.js (agregados + GeoJSON embebidos)
  ```
- **Publicar** (GitHub Pages, como los otros dashboards): `git add -A && git commit && git push`.

> **Consolidación / deduplicación.** Cada siniestro puede venir en un archivo nacional (solo urbano) y
> en uno regional (con rural). Se unen todas las capas de siniestros individuales y se **deduplica por
> `id_accidente`** (prefiriendo el registro regional, que incluye la zona rural) → combina urbano+rural
> sin doble conteo. Resultado: `data/parquet/siniestros_consolidado.parquet` (375.489 siniestros
> 2014–2024; el dashboard usa 2020–2024, ~290 mil).

---

## Los datos

Recopilación exhaustiva de capas georreferenciadas (shapefiles) de **estadísticas de
siniestros de tránsito en Chile**, base del dashboard.

## Qué se descargó

| Carpeta | Contenido | N.º capas | Fuente |
|---|---|---:|---|
| `data/CONASET/` | Siniestros de tránsito georreferenciados (puntos), por tema/región/año | **162** shapefiles | [Portal ArcGIS Open Data CONASET](https://mapas-conaset.opendata.arcgis.com) |
| `data/Cartografia_base/` | DPA Censal 2017 (comunas/provincias/regiones, con población) + Red Vial Nacional | 4 archivos | [Esri Chile / Censo](https://hub.arcgis.com) · [OCUC/IDE](https://ideocuc-ocuc.hub.arcgis.com) |

Todas las capas en **datum WGS84**, formato **Shapefile (.zip)**.

> ⚡ **Para análisis usa la capa Parquet, no los shapefiles crudos.** Todo fue convertido a
> **GeoParquet + DuckDB** en `data/parquet/` — ver [sección siguiente](#formato-eficiente-parqu--duckdb).

### CONASET — temas cubiertos (`data/CONASET/`)

| Carpeta | Tema | Capas |
|---|---|---:|
| `01_Puntos_criticos` | Puntos críticos de siniestralidad | 11 |
| `02_Atropellos` | Atropellos | 11 |
| `03_Siniestros_individuales` | Siniestros individuales (georreferenciados uno a uno), por región y año | 88 |
| `04_Siniestros_en_ruta` | Siniestros en ruta (interurbano) | 5 |
| `05_Motocicletas` | Siniestros con participación de motocicletas | 5 |
| `06_Bicicletas` | Siniestros con participación de bicicletas | 5 |
| `07_Siniestros_urbanos` | Siniestros urbanos por región (2024) | 15 |
| `08_Region_multianual` | Series regionales multianuales (p.ej. Biobío 2015–2023) | 22 |

**Cobertura temporal:** 2014 – 2024 (mayor densidad 2018–2024).
**Cobertura geográfica:** las 16 regiones del país (a nivel nacional, regional y de grandes ciudades).

Catálogo detallado, capa por capa: [`data/CATALOGO_CONASET.md`](data/CATALOGO_CONASET.md).

## Formato eficiente (Parquet + DuckDB)

Toda la información fue convertida a **GeoParquet** (columnar, comprimido zstd, geometría WGS84) en
`data/parquet/`, más una base **DuckDB** con vistas listas para consultar. Consultas sobre 544 mil
siniestros corren en **~50 ms**.

| Archivo | Descripción | Filas |
|---|---|---:|
| `data/parquet/siniestros_individuales.parquet` | **Tabla principal**: todos los siniestros individuales | 544.561 |
| `data/parquet/atropellos.parquet` | Atropellos | 43.724 |
| `data/parquet/siniestros_en_ruta.parquet` | Siniestros en ruta (interurbano) | 78.624 |
| `data/parquet/motocicletas.parquet` · `bicicletas.parquet` | Cortes por vehículo | 34.414 · 13.366 |
| `data/parquet/siniestros_urbanos.parquet` | Urbanos por región 2024 | 56.932 |
| `data/parquet/region_multianual.parquet` | Series regionales multianuales | 59.446 |
| `data/parquet/puntos_criticos.parquet` | Puntos críticos (agregados) | 382.001 |
| `data/parquet/cartografia/comunas.parquet` | 345 comunas (polígonos, **con población**) → coropletas y tasas | 345 |
| `data/parquet/cartografia/regiones.parquet` · `provincias.parquet` | 16 regiones · 56 provincias | 16 · 56 |
| `data/parquet/cartografia/red_vial.parquet` | Red Vial Nacional (líneas) | 316.246 |

**Qué se homogeneizó en la conversión** (ver [`data/parquet/DICCIONARIO.md`](data/parquet/DICCIONARIO.md)):
- **Encoding corregido** (ftfy): tildes y ñ correctas en todas las capas y "eras" de esquema.
- **Columnas canónicas** homogéneas presentes en todas las filas (`fecha`, `anio`, `region_norm`,
  `cod_region`, `comuna`, `cut_com`, `zona`, `tipo_final`, `causa_final`, `fallecidos`, `graves`,
  `menos_graves`, `leves`, `lat`, `lon`, …) **+** todas las columnas originales conservadas (`o_*`).
- **Región normalizada** a catálogo de 16 (`region_norm` + código CUT `cod_region`), unificando las ~37
  grafías originales (números romanos, mayúsculas, nombres).
- **`cut_com` rellenado** desde el nombre de comuna vía catálogo DPA → **97–100%** de cobertura de la
  llave de join comunal (join con `cartografia/comunas` = 100% de match).
- **`anio` saneado** a 2014–2024 (se descartaron fechas erróneas de origen: 1899, 2029, etc.).

### Uso

```python
import duckdb
con = duckdb.connect('data/accidentes.duckdb')   # vistas: siniestros, atropellos, carto_comunas, ...
con.load_extension('spatial')
con.sql("SELECT anio, sum(fallecidos) FROM siniestros GROUP BY anio ORDER BY anio").df()
```

- Vista **`siniestros`** = `siniestros_individuales` filtrada a `nivel='regional'` (incluye zona rural).
- Ejemplos ejecutables en [`scripts/consultar_ejemplo.py`](scripts/consultar_ejemplo.py).

> ⚠️ **Doble conteo — importante.** En `siniestros_individuales`, cada año 2020–2024 aparece **dos veces**:
> `nivel='nacional'` (archivo anual, **solo urbano**) y `nivel='regional'` (archivos por región, **con
> rural**). Para una serie nacional, filtrar a **uno** de los dos por año — nunca sumar ambos. Los temas
> `atropellos`, `motocicletas`, `bicicletas`, `urbanos`, `en_ruta` son **subconjuntos** de los siniestros
> individuales (por tipo/vehículo/zona), no sumar con la tabla principal.

### Reproducir la conversión

```bash
python scripts/convertir_parquet.py     # shapefiles -> GeoParquet
python scripts/crear_duckdb.py          # crea data/accidentes.duckdb con vistas
python scripts/generar_diccionario.py   # regenera el diccionario de datos
```

## Modelo de datos (capa de siniestros individuales)

Cada punto = un siniestro geolocalizado. Campos principales:

| Campo | Descripción |
|---|---|
| `IdAccident` | Identificador único del siniestro |
| `Fecha`, `Mes`, `Diames`, `Diasemana`, `Hora`, `Año` | Temporalidad |
| `Región`, `Comuna`, `Ciudad`, `Zona` | Ubicación (`Zona` = URBANA/RURAL) |
| `CUT_REG`, `CUT_COM` | Códigos únicos territoriales (para joins con cartografía) |
| `Tipo__CONA` | Tipo de siniestro (colisión, atropello, volcadura, etc.) |
| `Causa__CON` | Causa (imprudencia del conductor, etc.) |
| `Fallecidos`, `Graves`, `Menos_Grav`, `Leves`, `Lesionados` | Consecuencias / severidad |
| `Lat`, `Lon` | Coordenadas |

> Ejemplo de volumen: la capa nacional urbana 2020 contiene **48.723** siniestros.

## Archivos de soporte

- `data/conaset_dcat.json` — catálogo DCAT completo del portal (166 datasets, con URLs de descarga en CSV/GeoJSON/KML/Shapefile/REST).
- `data/conaset_manifest.csv` — manifiesto tabular (título, tema, año, y URL de descarga de cada formato).
- `data/CONASET/_descarga_log.csv` — log de la descarga (estado y tamaño por capa).
- `descargar_conaset.py` — script reproducible que regenera todas las descargas desde el DCAT.

## Notas sobre las fuentes

- **CONASET** (Comisión Nacional de Seguridad de Tránsito) es el organismo oficial de estadísticas
  de siniestralidad vial en Chile; sus datos provienen de partes de Carabineros. Es **la** fuente
  de datos de accidentes georreferenciados del país.
- 4 de los 166 datasets del catálogo no ofrecen distribución shapefile (solo tabla/mapa); el resto
  (162) se descargó completo, sin fallas.
- Datos referenciales, actualizados periódicamente por CONASET; puede haber diferencias con cifras
  oficiales consolidadas.

## Próximos pasos sugeridos para el dashboard

1. ~~Consolidar los siniestros individuales en una única base (geoparquet).~~ ✅ hecho (`data/parquet/`).
2. ~~Unir con la DPA por `cut_com`/`cod_region`.~~ ✅ llaves listas y validadas (join 100%).
3. Definir la deduplicación de la serie nacional (elegir nacional-urbano vs regional-con-rural por año).
4. Definir KPIs: siniestros, fallecidos, tasa por 100k hab. (población ya en `carto_comunas`),
   severidad, por año/comuna/tipo/causa.
5. Construir el dashboard (mapa de calor + coropletas + filtros por año/región/tipo), en línea con los
   otros dashboards de RMG.
