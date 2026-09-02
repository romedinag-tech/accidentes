# -*- coding: utf-8 -*-
"""
Pipeline del dashboard de siniestros de tránsito (CONASET).
Genera data_bundle.js (window.DATA) con agregados + GeoJSON simplificado, embebidos para uso offline.

Flujo completo (desde los shapefiles):
    python scripts/convertir_parquet.py   # shapefiles -> GeoParquet
    python scripts/consolidar.py          # -> siniestros_consolidado.parquet (dedup por id)
    python procesar_accidentes.py         # -> data_bundle.js  (este script)

Alcance del dashboard: 2020-2024 (años con cobertura nacional completa = 16 regiones).
"""
import os, json, datetime, warnings
import duckdb, geopandas as gpd, pandas as pd
from shapely import set_precision
warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, 'data', 'parquet').replace('\\', '/')
CONS = f'{P}/siniestros_consolidado.parquet'
ANIO_MIN, ANIO_MAX = 2020, 2024
N_CAUSAS = 12          # causas principales; el resto -> "OTRAS CAUSAS"
BUILD = os.environ.get('BUILD_STAMP') or datetime.date.today().isoformat()

con = duckdb.connect()
con.load_extension('spatial')

def q(sql):
    return con.execute(sql).df()

WHERE = f"anio BETWEEN {ANIO_MIN} AND {ANIO_MAX} AND cod_region IS NOT NULL"
SRC = f"read_parquet('{CONS}')"
# zona -> 0 URBANA, 1 RURAL, 2 sin dato
ZONA = "CASE zona WHEN 'URBANA' THEN 0 WHEN 'RURAL' THEN 1 ELSE 2 END"

# ---------- catálogos ----------
regiones = q(f"""
    SELECT cod_region, any_value(region_norm) nombre
    FROM {SRC} WHERE {WHERE} GROUP BY cod_region ORDER BY cod_region
""")
reg_pob = q(f"SELECT cod_region, poblacion FROM read_parquet('{P}/cartografia/regiones.parquet')")
reg_pob = dict(zip(reg_pob.cod_region, reg_pob.poblacion))
REGIONES = [{'cod': int(r.cod_region), 'nombre': r.nombre, 'poblacion': int(reg_pob.get(r.cod_region) or 0)}
            for r in regiones.itertuples()]

tipos = q(f"SELECT coalesce(tipo_final,'SIN DATO') t, count(*) n FROM {SRC} WHERE {WHERE} GROUP BY 1 ORDER BY n DESC")
TIPOS = list(tipos.t)
tipo_idx = {t: i for i, t in enumerate(TIPOS)}

causas = q(f"SELECT coalesce(causa_final,'SIN DATO') c, count(*) n FROM {SRC} WHERE {WHERE} GROUP BY 1 ORDER BY n DESC")
CAUSAS = list(causas.c[:N_CAUSAS]) + ['OTRAS CAUSAS']
causa_idx = {c: i for i, c in enumerate(CAUSAS[:-1])}
OTRAS = len(CAUSAS) - 1

comunas = q(f"""
    SELECT c.cut_com, any_value(c.comuna) nombre, any_value(c.cod_region) cod_region,
           any_value(c.poblacion) poblacion
    FROM read_parquet('{P}/cartografia/comunas.parquet') c
    GROUP BY c.cut_com ORDER BY c.cut_com
""")
COMUNAS = [{'cut': r.cut_com, 'nombre': r.nombre, 'cod': int(r.cod_region), 'pob': int(r.poblacion or 0)}
           for r in comunas.itertuples()]
com_idx = {r['cut']: i for i, r in enumerate(COMUNAS)}

# ---------- hechos ----------
def metrics(extra_cols, extra_group):
    return q(f"""
        SELECT {extra_cols},
               count(*) s, sum(fallecidos) m, sum(graves) g,
               sum(menos_graves) mg, sum(leves) l
        FROM {SRC} WHERE {WHERE} GROUP BY {extra_group}
    """)

# factGeo: comuna x año x tipo x zona
fg = metrics(f"cut_com, anio, coalesce(tipo_final,'SIN DATO') tipo, {ZONA} zona",
             f"cut_com, anio, coalesce(tipo_final,'SIN DATO'), {ZONA}")
FACT_GEO = [[com_idx[r.cut_com], int(r.anio), tipo_idx[r.tipo], int(r.zona),
             int(r.s), int(r.m or 0), int(r.g or 0), int(r.mg or 0), int(r.l or 0)]
            for r in fg.itertuples() if r.cut_com in com_idx]

def temporal(dim_sql):
    df = metrics(f"cod_region, anio, {dim_sql} d, {ZONA} zona", f"cod_region, anio, {dim_sql}, {ZONA}")
    return [[int(r.cod_region), int(r.anio), int(r.d), int(r.zona), int(r.s), int(r.m or 0)]
            for r in df.itertuples() if pd.notna(r.d)]

FACT_MES = temporal('mes')
FACT_HORA = temporal('hora')
FACT_DIA = temporal('dia_semana')

# causa: cod_region x año x causaIdx x zona
fc = metrics(f"cod_region, anio, coalesce(causa_final,'SIN DATO') causa, {ZONA} zona",
             f"cod_region, anio, coalesce(causa_final,'SIN DATO'), {ZONA}")
FACT_CAUSA = [[int(r.cod_region), int(r.anio), causa_idx.get(r.causa, OTRAS), int(r.zona),
               int(r.s), int(r.m or 0)] for r in fc.itertuples()]

# gridHot: puntos agregados en grilla (~330 m) para el mapa de calor / zonas de concentración.
# Acumulado 2020-2024, etiquetado por comuna para poder filtrar al hacer zoom a una ciudad.
BIN = 0.003
gh = q(f"""
    SELECT round(lat/{BIN})*{BIN} la, round(lon/{BIN})*{BIN} lo, cut_com,
           count(*) s, sum(fallecidos) m
    FROM {SRC}
    WHERE {WHERE} AND lat IS NOT NULL AND lon IS NOT NULL
      AND lat BETWEEN -56 AND -17 AND lon BETWEEN -110 AND -66
    GROUP BY 1, 2, cut_com
""")
GRID_HOT = [[round(r.la, 3), round(r.lo, 3), com_idx[r.cut_com], int(r.s), int(r.m or 0)]
            for r in gh.itertuples() if r.cut_com in com_idx]

# ---------- GeoJSON simplificado ----------
def round_coords(obj, nd=3):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(x, nd) for x in obj]
        return [round_coords(o, nd) for o in obj]
    return obj

def geojson(path, cols, tol):
    g = gpd.read_parquet(path)[cols + ['geometry']].copy()
    g['geometry'] = g.geometry.buffer(0).simplify(tol, preserve_topology=True)
    gj = json.loads(g.to_json())
    for f in gj['features']:
        f.pop('id', None)
        f['geometry']['coordinates'] = round_coords(f['geometry']['coordinates'])
    return gj

GJ_COMUNAS = geojson(f'{P}/cartografia/comunas.parquet', ['cut_com'], 0.012)
GJ_REGIONES = geojson(f'{P}/cartografia/regiones.parquet', ['cod_region'], 0.02)

# ---------- serie de cobertura (para nota honesta) ----------
cob = q(f"""SELECT anio, count(*) s, count(DISTINCT cod_region) regiones
            FROM {SRC} WHERE anio BETWEEN 2014 AND 2024 GROUP BY anio ORDER BY anio""")
COBERTURA = [[int(r.anio), int(r.s), int(r.regiones)] for r in cob.itertuples()]

DATA = {
    'meta': {
        'generado': BUILD,
        'anios': list(range(ANIO_MIN, ANIO_MAX + 1)),
        'fuente': 'CONASET — Observatorio de Datos de Seguridad de Tránsito',
        'nota': ('Siniestros georreferenciados 2020–2024 (cobertura nacional, 16 regiones). '
                 'La georreferenciación es principalmente urbana; la cobertura rural es parcial '
                 '(mayor en 2020–2022). Datos deduplicados por id de siniestro.'),
        'regiones': REGIONES, 'tipos': TIPOS, 'causas': CAUSAS,
        'zonas': ['Urbana', 'Rural', 'Sin dato'],
        'dias': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
        'cobertura': COBERTURA,
    },
    'comunas': COMUNAS,
    'factGeo': FACT_GEO,
    'factMes': FACT_MES, 'factHora': FACT_HORA, 'factDia': FACT_DIA, 'factCausa': FACT_CAUSA,
    'gridHot': GRID_HOT,
    'geoComunas': GJ_COMUNAS, 'geoRegiones': GJ_REGIONES,
}

out = os.path.join(BASE, 'data_bundle.js')
with open(out, 'w', encoding='utf-8') as f:
    f.write('/* Generado por procesar_accidentes.py — no editar a mano. */\n')
    f.write('window.DATA = ')
    json.dump(DATA, f, ensure_ascii=False, separators=(',', ':'))
    f.write(';\n')

mb = os.path.getsize(out) / 1e6
print(f'data_bundle.js -> {mb:.2f} MB')
print(f'  factGeo={len(FACT_GEO)}  factMes={len(FACT_MES)}  factHora={len(FACT_HORA)} '
      f'factDia={len(FACT_DIA)}  factCausa={len(FACT_CAUSA)}  gridHot={len(GRID_HOT)}')
print(f'  comunas={len(COMUNAS)}  regiones={len(REGIONES)}  tipos={len(TIPOS)}  causas={len(CAUSAS)}')
print(f'  geoComunas={len(GJ_COMUNAS["features"])} feats  geoRegiones={len(GJ_REGIONES["features"])} feats')
con.close()
