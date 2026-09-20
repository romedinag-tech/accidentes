# Dashboard de siniestralidad vial

## Propósito

Dashboard de siniestros de tránsito en Chile con lectura territorial por comuna, región y punto,
publicado en https://romedinag-tech.github.io/accidentes/ . Dos fuentes conmutables desde el título:
la dimensión **[conaset]** (datos abiertos de CONASET, 2020–2025, georreferenciados) y la dimensión
**[os2]** (Carabineros O.S.2, histórico 2010–2025, universo distinto y más profundo, geocodificado por
nosotros). Son dos universos del mismo fenómeno; **no se suman**.

## Estado

activo

Publicado y operativo. Un conmutador de fuente bajo el título abre las mismas tres secciones —Siniestros ·
Personas · Análisis espacial— para las dos fuentes. Última actividad: 2026-09-19.

Encargo del orquestador `siniestralidad.columna-vertebral-v2` (hub → siniestralidad): **respondido** en
esta pasada; lo cierra el hub tras verificar.

### [conaset]
Base 2020–2025 (436.521), personas (770.414), riesgo hexagonal, análisis espacial deck.gl (puntos,
concentración, comunas, riesgo hex, relieve KDE, red vial). Filtros Región/Comuna/Año/Zona/Modo.

### [os2]
1,24 M siniestros 2010–2025 integrados como subsistema paralelo (reusa el mismo `state`; los filtros
Región/Comuna/Año manejan ambas fuentes, Zona/Modo son solo-CONASET). Aporta lo que CONASET no publica:
modo, letalidad por modo, tipo de vehículo, dado a la fuga, causa detallada (59), ranking de ciudades
normalizado, mapa de densidad por modo (calor/hex) y **selector Total/Urbano/Rural por figura**.
Geocodificación propia: **78 % con punto, 100 % dentro de su comuna**.

## Entradas y salidas

Contrato completo en [`SALIDAS.md`](SALIDAS.md). Producto publicado: `index.html` + `data_bundle.js`
(CONASET) + `os2_bundle.js` (O.S.2) + `data/os2hex/<reg>.json` (densidad por modo, lazy-load).

**QUÉ PRODUCE**

### [conaset]
1. **El dashboard** (`index.html` + `data_bundle.js`) — el producto publicado.
2. **La base canónica** (`data/parquet/siniestros_2020_2025.parquet`, 436.521 siniestros 2020–2025,
   urbano+rural, todos georreferenciados). La antigua `siniestros_consolidado.parquet` (375.489,
   2020–2024) quedó **superada** por ésta.
3. **La base a nivel persona** (`data/parquet/personas.parquet`, 770.414 personas 2020–2024) — alimenta
   la pestaña "Personas accidentadas".
4. **El riesgo hexagonal** (`data/riesgo/<cod_region>.json`, 6.275 hexágonos H3 res-8, tasa
   siniestros÷población Censo 2024).
5. **Cartografía lista para unir** (`comunas.parquet` 345, `regiones.parquet` 16).

### [os2]
6. **Base canónica O.S.2** (`data/OS2/parquet/os2_{siniestros,personas,vehiculos}.parquet` + `os2.duckdb`)
   — 1.238.336 / 2.509.370 / 2.192.523, unibles por `id_accidente`.
7. **O.S.2 geocodificado** (`os2_siniestros_geo.parquet`, 970.845 con lat/lon = 78 %) → `os2_bundle.js`
   (agregados por comuna×año×sector) + `data/os2hex/<reg>.json` (densidad por modo).

**QUÉ CONSUME.** CONASET: los FeatureServer del portal ArcGIS de CONASET (scripts `descargar_*`) y la
población por manzana del **Censo 2024** (`censo2024_manzana_entidad.parquet`, solo lectura desde otro
proyecto). O.S.2: 48 Excel de Carabineros (Transparencia Proactiva O.S.2) y el **activo Red Vial de Chile
(SOLO LECTURA)** para geocodificar (red detallada 345 comunas + red MOP + su `config.py` de conurbaciones).

**Cifras de control:** Chile, 16 regiones. CONASET **436.521 siniestros** (Base_SINIESTROS_2020_2025) ·
770.414 personas. O.S.2 **1.238.336 siniestros** (2010–2025) · 970.845 geocodificados (78 %). Llave
`cut_com` con join contra la cartografía comunal.

## Datos canónicos

### [conaset]
- `data\parquet\siniestros_2020_2025.parquet` — **la base del dashboard hoy** (436.521, 2020–2025,
  urbano+rural, con banderas de modo Atropello/Bicicleta/Motociclet y `CAUSA_NUEV`). Usar ésta.
- `data\parquet\personas.parquet` — 770.414 personas (edad, sexo, rol, tipo de usuario CONASET).
- `data\parquet\cartografia\comunas.parquet` (345) y `regiones.parquet` (16).
- `data\parquet\siniestros_consolidado.parquet` + `data\accidentes.duckdb` — dedup 2020–2024 (375.489),
  **legado**: sigue en disco pero el dashboard ya no lo usa. Para análisis nuevos, preferir la 2020–2025.

### [os2]
- `data\OS2\parquet\os2_siniestros.parquet` (1.238.336) · `os2_personas.parquet` (2.509.370) ·
  `os2_vehiculos.parquet` (2.192.523) — Carabineros O.S.2 2010–2025, unibles por `id_accidente`.
- `data\OS2\parquet\os2_siniestros_geo.parquet` — siniestros con lat/lon (78 %). 🔴 coords a nivel
  siniestro individual → publicar SOLO agregado a hex/comuna.
- `data\OS2\os2.duckdb` — 3 tablas; la tabla `siniestros` trae las coordenadas.
- Los pesados de O.S.2 (`data/OS2/`) y los bundles quedan gitignored, fuera del repo del sitio.

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
- **[os2] 2026-09-05 — Geocodificar contra la RED DETALLADA (345 comunas), no el maestro INE (152):** la
  intersección por nodo compartido del grafo llevó la cobertura de 45 % a 78 %. Las rutas van por
  `nombre_ruta` en la red detallada (trae las menores que la red MOP interurbana no tiene). Ruta+km se
  **ancla a la comuna** del siniestro (un km chico en "Ruta 5" caía a 472 km del sitio).
- **[os2] 2026-09-05 — `'CAMION' in 'CAMIONETA'`:** clasificar camioneta ANTES que camión en el mapeo de
  modo, o las 314 k camionetas quedan mal contadas como camión.
- **[os2] 2026-09-06 — Los JSON de hex van en `data/os2hex/`, NO `data/os2/`:** en Windows
  (case-insensitive) `data/os2/` colisiona con `data/OS2/` (gitignored) y esos JSON no se publican en
  Pages (Linux, case-sensitive) → el mapa se rompe en producción, no en local.
- **[os2] 2026-09-06 — `leaflet.heat` revienta (`getImageData` con canvas 0 px)** si el contenedor está
  oculto y redibuja async por eventos del mapa. Guardas: retirar la capa al salir del espacial, guarda de
  tamaño, wrap de `_heat.draw`, y `preventDefault` de `error`/`unhandledrejection` SOLO para `/getImageData/`.
- **2026-09-06 — Cambiar la FORMA de un fact** (los facts de 6 a 7 columnas al agregar zona) **obliga
  cache-bust `?v=N`** del bundle y de los JSON lazy, o el JS nuevo lee el layout viejo y rompe en silencio.
- **[os2] 2026-09-19 — Dos runs full del geocodificador al MISMO parquet: gana el que termina último.** Uno
  viejo (maestro-INE, 50 %) terminó tarde y pisó el bueno (red detallada, 78 %); el bundle y los hexágonos
  publicados salieron del malo dos semanas. Lo delató que la columna decía 78 % y el archivo daba 50 %.
  Escribir a un `.NEW` y `os.replace` sólo si verifica; nunca dos runs full al mismo destino.

## Cómo se ejecuta

```bash
# Pipeline CONASET (base 2020-2025 + personas + espacial)
python scripts/descargar_base_2025.py    # baja Base_SINIESTROS_2020_2025 (FeatureServer, paginado)
python scripts/convertir_base_2025.py    # -> data/parquet/siniestros_2020_2025.parquet
python scripts/descargar_personas.py     # baja Base_de_persona_vehiculo_4 (paso = maxRecordCount)
python scripts/convertir_personas.py     # -> data/parquet/personas.parquet
python scripts/segmentar_red_vial.py     # accidentes -> tramos de Red Vial Nacional (linear referencing)
python scripts/riesgo_hexagonal.py       # -> data/riesgo/<cod>.json (riesgo H3 x poblacion Censo 2024)
python procesar_accidentes.py            # -> data_bundle.js + data/puntos|redvial/<cod>.json

# Base O.S.2 de Carabineros (2010-2025, historico, SEPARADO de CONASET) -- ver data/OS2/FUENTE.md
python scripts/convertir_os2.py          # 48 Excel -> 3 parquets canonicos + os2.duckdb
python scripts/geocodificar_os2.py       # geocodifica con Red Vial detallada (solo lectura), a un .NEW
                                         #   -> os2_siniestros_geo.parquet (78%, 100% en comuna)
python procesar_os2.py                   # -> os2_bundle.js + data/os2hex/<reg>.json (agregados + densidad por modo)
```

<!-- columna-vertebral: ultima_actualizacion=2026-09-19 commit=7a02169 -->
