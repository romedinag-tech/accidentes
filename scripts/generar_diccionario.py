# -*- coding: utf-8 -*-
"""Genera data/parquet/DICCIONARIO.md a partir de los parquet reales."""
import geopandas as gpd, glob, os, warnings
warnings.filterwarnings('ignore')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

CANON_DESC = {
 'id_accidente':'ID único del siniestro (CONASET)','fecha':'Fecha del siniestro (timestamp UTC)',
 'anio':'Año (2014-2024, saneado)','mes':'Mes (1-12)','dia_mes':'Día del mes','dia_semana':'Día de la semana',
 'hora':'Hora','region':'Región (texto original crudo)','region_norm':'Región normalizada (catálogo de 16)',
 'cod_region':'Código CUT de región (1-16)','provincia':'Provincia','comuna':'Comuna (texto crudo)',
 'cut_reg':'Código CUT región','cut_prov':'Código CUT provincia','cut_com':'Código CUT comuna (join con cartografía)',
 'ciudad':'Ciudad','zona':'URBANA / RURAL','tipo':'Tipo de accidente (Carabineros)',
 'tipo_conaset':'Tipo según clasificación CONASET','tipo_final':'Tipo (coalesce CONASET/Carabineros)',
 'causa':'Causa (Carabineros)','causa_conaset':'Causa CONASET','causa_final':'Causa (coalesce)',
 'ubicacion':'Ubicación relativa','calle_1':'Calle 1','calle_2':'Calle 2','numero':'Numeración','ruta':'Ruta',
 'fallecidos':'N.º fallecidos','graves':'N.º lesionados graves','menos_graves':'N.º menos graves',
 'leves':'N.º leves','lesionados':'N.º lesionados','n_accidentes':'N.º accidentes (capas agregadas)',
 'lat':'Latitud (WGS84)','lon':'Longitud (WGS84)','geometry':'Punto WGS84',
 'region_nombre':'Nombre oficial de región','poblacion':'Población (Censo 2017)',
 'superficie_km2':'Superficie km²','densidad_hab_km2':'Densidad hab/km²','viviendas':'N.º viviendas',
}
META = ['tema','capa_origen','anio_archivo','region_archivo','nivel']
L = ['# Diccionario de datos — Parquet', '',
     'Todas las capas en **GeoParquet** (geometría WGS84/EPSG:4326, compresión zstd).',
     'En las capas de siniestros, las columnas **canónicas** (homogéneas entre capas y eras de esquema) van primero;',
     'las columnas `o_*` conservan los campos originales del shapefile (sin pérdida de información).', '',
     '> **Nota anti-doble-conteo:** en `siniestros_individuales`, `nivel=nacional` son archivos anuales'
     ' **solo urbanos** y `nivel=regional` son archivos por región **con zona rural**. Para series nacionales'
     ' usar uno u otro por año, no ambos (ver README).', '']

def section(path, carto=False):
    g = gpd.read_parquet(path)
    slug = os.path.basename(path)[:-8]
    L.append(f'## `{slug}.parquet` — {len(g):,} filas · {len(g.columns)} columnas'.replace(',', '.'))
    canon = [c for c in g.columns if not c.startswith('o_') and c not in META]
    L.append('| Columna | Tipo | Descripción |')
    L.append('|---|---|---|')
    for c in canon:
        desc = CANON_DESC.get(c, '')
        L.append(f'| `{c}` | {g[c].dtype} | {desc} |')
    if not carto:
        L.append(f'| `{", ".join(META)}` | | metadatos de procedencia |')
        norig = sum(1 for c in g.columns if c.startswith('o_'))
        if norig:
            L.append(f'| `o_*` | | {norig} columnas originales del shapefile |')
    L.append('')

for f in sorted(glob.glob('data/parquet/*.parquet')):
    section(f)
L.append('---')
L.append('## Cartografía base (`data/parquet/cartografia/`)')
L.append('')
for f in sorted(glob.glob('data/parquet/cartografia/*.parquet')):
    section(f, carto=True)

open('data/parquet/DICCIONARIO.md', 'w', encoding='utf-8').write('\n'.join(L))
print('DICCIONARIO.md escrito:', len(L), 'lineas')
