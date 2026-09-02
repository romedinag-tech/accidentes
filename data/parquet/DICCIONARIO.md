# Diccionario de datos — Parquet

Todas las capas en **GeoParquet** (geometría WGS84/EPSG:4326, compresión zstd).
En las capas de siniestros, las columnas **canónicas** (homogéneas entre capas y eras de esquema) van primero;
las columnas `o_*` conservan los campos originales del shapefile (sin pérdida de información).

> **Nota anti-doble-conteo:** en `siniestros_individuales`, `nivel=nacional` son archivos anuales **solo urbanos** y `nivel=regional` son archivos por región **con zona rural**. Para series nacionales usar uno u otro por año, no ambos (ver README).

## `atropellos.parquet` — 43.724 filas · 84 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | int32 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ms, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | int32 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | int64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | str | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | str | Código CUT región |
| `cut_prov` | str | Código CUT provincia |
| `cut_com` | str | Código CUT comuna (join con cartografía) |
| `ciudad` | float64 | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | str | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | str | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | str | Ubicación relativa |
| `calle_1` | str | Calle 1 |
| `calle_2` | str | Calle 2 |
| `numero` | float64 | Numeración |
| `ruta` | str | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | int32 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | int32 | N.º leves |
| `lesionados` | float64 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 42 columnas originales del shapefile |

## `bicicletas.parquet` — 13.366 filas · 84 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | int32 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ms, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | int32 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | int64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | str | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | str | Código CUT región |
| `cut_prov` | str | Código CUT provincia |
| `cut_com` | str | Código CUT comuna (join con cartografía) |
| `ciudad` | float64 | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | str | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | str | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | str | Ubicación relativa |
| `calle_1` | str | Calle 1 |
| `calle_2` | str | Calle 2 |
| `numero` | int32 | Numeración |
| `ruta` | str | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | int32 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | int32 | N.º leves |
| `lesionados` | float64 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 42 columnas originales del shapefile |

## `motocicletas.parquet` — 34.414 filas · 84 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | int32 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ms, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | int32 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | int64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | str | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | str | Código CUT región |
| `cut_prov` | str | Código CUT provincia |
| `cut_com` | str | Código CUT comuna (join con cartografía) |
| `ciudad` | float64 | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | str | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | str | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | str | Ubicación relativa |
| `calle_1` | str | Calle 1 |
| `calle_2` | str | Calle 2 |
| `numero` | float64 | Numeración |
| `ruta` | str | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | int32 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | int32 | N.º leves |
| `lesionados` | float64 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 42 columnas originales del shapefile |

## `puntos_criticos.parquet` — 382.001 filas · 56 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | float64 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ms, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | float64 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | float64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | str | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | float64 | Código CUT región |
| `cut_prov` | float64 | Código CUT provincia |
| `cut_com` | float64 | Código CUT comuna (join con cartografía) |
| `ciudad` | float64 | Ciudad |
| `zona` | float64 | URBANA / RURAL |
| `tipo` | float64 | Tipo de accidente (Carabineros) |
| `tipo_conaset` | float64 | Tipo según clasificación CONASET |
| `causa` | float64 | Causa (Carabineros) |
| `causa_conaset` | float64 | Causa CONASET |
| `ubicacion` | float64 | Ubicación relativa |
| `calle_1` | float64 | Calle 1 |
| `calle_2` | float64 | Calle 2 |
| `numero` | float64 | Numeración |
| `ruta` | float64 | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | float64 | N.º lesionados graves |
| `menos_graves` | float64 | N.º menos graves |
| `leves` | float64 | N.º leves |
| `lesionados` | int32 | N.º lesionados |
| `n_accidentes` | int32 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | float64 | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | float64 | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 14 columnas originales del shapefile |

## `region_multianual.parquet` — 59.446 filas · 126 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | float64 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ns, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | float64 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | float64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | float64 | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | float64 | Código CUT región |
| `cut_prov` | float64 | Código CUT provincia |
| `cut_com` | float64 | Código CUT comuna (join con cartografía) |
| `ciudad` | float64 | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | str | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | str | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | str | Ubicación relativa |
| `calle_1` | str | Calle 1 |
| `calle_2` | str | Calle 2 |
| `numero` | str | Numeración |
| `ruta` | float64 | Ruta |
| `fallecidos` | float64 | N.º fallecidos |
| `graves` | float64 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | float64 | N.º leves |
| `lesionados` | float64 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 84 columnas originales del shapefile |

## `siniestros_en_ruta.parquet` — 78.624 filas · 68 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | int32 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ms, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | int32 | Mes (1-12) |
| `dia_mes` | int32 | Día del mes |
| `dia_semana` | int32 | Día de la semana |
| `hora` | int64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | float64 | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | str | Código CUT región |
| `cut_prov` | float64 | Código CUT provincia |
| `cut_com` | str | Código CUT comuna (join con cartografía) |
| `ciudad` | str | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | float64 | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | float64 | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | float64 | Ubicación relativa |
| `calle_1` | float64 | Calle 1 |
| `calle_2` | float64 | Calle 2 |
| `numero` | float64 | Numeración |
| `ruta` | float64 | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | int32 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | int32 | N.º leves |
| `lesionados` | int32 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 26 columnas originales del shapefile |

## `siniestros_individuales.parquet` — 544.561 filas · 161 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | int32 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[ms, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | float64 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | float64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | float64 | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | float64 | Código CUT región |
| `cut_prov` | float64 | Código CUT provincia |
| `cut_com` | float64 | Código CUT comuna (join con cartografía) |
| `ciudad` | str | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | str | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | str | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | str | Ubicación relativa |
| `calle_1` | str | Calle 1 |
| `calle_2` | str | Calle 2 |
| `numero` | str | Numeración |
| `ruta` | float64 | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | int32 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | int32 | N.º leves |
| `lesionados` | float64 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 119 columnas originales del shapefile |

## `siniestros_urbanos.parquet` — 56.932 filas · 73 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `id_accidente` | int32 | ID único del siniestro (CONASET) |
| `fecha` | datetime64[us, UTC] | Fecha del siniestro (timestamp UTC) |
| `anio` | Int64 | Año (2014-2024, saneado) |
| `mes` | float64 | Mes (1-12) |
| `dia_mes` | float64 | Día del mes |
| `dia_semana` | float64 | Día de la semana |
| `hora` | float64 | Hora |
| `region` | str | Región (texto original crudo) |
| `provincia` | float64 | Provincia |
| `comuna` | str | Comuna (texto crudo) |
| `cut_reg` | float64 | Código CUT región |
| `cut_prov` | float64 | Código CUT provincia |
| `cut_com` | float64 | Código CUT comuna (join con cartografía) |
| `ciudad` | float64 | Ciudad |
| `zona` | str | URBANA / RURAL |
| `tipo` | str | Tipo de accidente (Carabineros) |
| `tipo_conaset` | str | Tipo según clasificación CONASET |
| `causa` | str | Causa (Carabineros) |
| `causa_conaset` | str | Causa CONASET |
| `ubicacion` | str | Ubicación relativa |
| `calle_1` | str | Calle 1 |
| `calle_2` | str | Calle 2 |
| `numero` | int32 | Numeración |
| `ruta` | float64 | Ruta |
| `fallecidos` | int32 | N.º fallecidos |
| `graves` | int32 | N.º lesionados graves |
| `menos_graves` | int32 | N.º menos graves |
| `leves` | int32 | N.º leves |
| `lesionados` | float64 | N.º lesionados |
| `n_accidentes` | float64 | N.º accidentes (capas agregadas) |
| `lat` | float64 | Latitud (WGS84) |
| `lon` | float64 | Longitud (WGS84) |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `tipo_final` | str | Tipo (coalesce CONASET/Carabineros) |
| `causa_final` | str | Causa (coalesce) |
| `geometry` | geometry | Punto WGS84 |
| `tema, capa_origen, anio_archivo, region_archivo, nivel` | | metadatos de procedencia |
| `o_*` | | 31 columnas originales del shapefile |

---
## Cartografía base (`data/parquet/cartografia/`)

## `comunas.parquet` — 345 filas · 14 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `cut_com` | int64 | Código CUT comuna (join con cartografía) |
| `comuna` | str | Comuna (texto crudo) |
| `cut_prov` | int64 | Código CUT provincia |
| `provincia` | str | Provincia |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `region_nombre` | str | Nombre oficial de región |
| `poblacion` | int32 | Población (Censo 2017) |
| `pob_hombres` | int32 |  |
| `pob_mujeres` | int32 |  |
| `viviendas` | int32 | N.º viviendas |
| `superficie_km2` | float64 | Superficie km² |
| `densidad_hab_km2` | float64 | Densidad hab/km² |
| `geometry` | geometry | Punto WGS84 |

## `provincias.parquet` — 56 filas · 23 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `objectid` | int32 |  |
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_nombre` | str | Nombre oficial de región |
| `cut_prov` | int64 | Código CUT provincia |
| `provincia` | str | Provincia |
| `t_hom_r` | int32 |  |
| `t_muj_r` | int32 |  |
| `t_pob_r` | int32 |  |
| `t_hom_u` | int32 |  |
| `t_muj_u` | int32 |  |
| `t_pob_u` | int32 |  |
| `t_hom` | int32 |  |
| `t_muj` | int32 |  |
| `poblacion` | int32 | Población (Censo 2017) |
| `t_viv_u` | int32 |  |
| `t_viv_r` | int32 |  |
| `t_viv` | int32 |  |
| `superficie` | float64 |  |
| `densidad` | float64 |  |
| `shape_leng` | float64 |  |
| `shape_are` | float64 |  |
| `shape_len` | float64 |  |
| `geometry` | geometry | Punto WGS84 |

## `red_vial.parquet` — 316.246 filas · 8 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `fid` | int32 |  |
| `type` | str |  |
| `nombre` | str |  |
| `comuna` | str | Comuna (texto crudo) |
| `nombre_reg` | str |  |
| `nombre_com` | str |  |
| `shape_len` | float64 |  |
| `geometry` | geometry | Punto WGS84 |

## `regiones.parquet` — 16 filas · 7 columnas
| Columna | Tipo | Descripción |
|---|---|---|
| `cod_region` | Int64 | Código CUT de región (1-16) |
| `region_norm` | str | Región normalizada (catálogo de 16) |
| `region_nombre` | str | Nombre oficial de región |
| `poblacion` | int32 | Población (Censo 2017) |
| `superficie_km2` | float64 | Superficie km² |
| `densidad_hab_km2` | float64 | Densidad hab/km² |
| `geometry` | geometry | Punto WGS84 |
