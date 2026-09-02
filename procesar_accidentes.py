# -*- coding: utf-8 -*-
"""
Pipeline del dashboard de siniestros de tránsito (CONASET).
Genera data_bundle.js (window.DATA) con agregados + GeoJSON simplificado, embebidos.

Base: Base_SINIESTROS_2020_2025 (CONASET) -> data/parquet/siniestros_2020_2025.parquet
Alcance: 2020-2025, urbano + rural, con MODO involucrado (Peatón/Moto/Bici/Vehículo)
y causa agrupada. Ver scripts/descargar_base_2025.py y scripts/convertir_base_2025.py.
"""
import os, json, datetime, warnings
import duckdb, geopandas as gpd, pandas as pd
import topojson as tp
warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, 'data', 'parquet').replace('\\', '/')
SRC = f"read_parquet('{P}/siniestros_2020_2025.parquet')"
ANIO_MIN, ANIO_MAX = 2020, 2025
BUILD = os.environ.get('BUILD_STAMP') or datetime.date.today().isoformat()
MODOS = ['Peatón', 'Motocicleta', 'Bicicleta', 'Vehículo']
modo_idx = {m: i for i, m in enumerate(MODOS)}

con = duckdb.connect()
con.load_extension('spatial')
def q(sql): return con.execute(sql).df()

WHERE = f"anio BETWEEN {ANIO_MIN} AND {ANIO_MAX} AND cod_region IS NOT NULL"
ZONA = "CASE zona WHEN 'URBANA' THEN 0 WHEN 'RURAL' THEN 1 ELSE 2 END"
MODO = "list_position(" + str(MODOS).replace("'", "'") + ", modo) - 1"  # 0..3

# ---------- catálogos ----------
regiones = q(f"SELECT cod_region, any_value(region_norm) nombre FROM {SRC} WHERE {WHERE} GROUP BY cod_region ORDER BY cod_region")
reg_pob = q(f"SELECT cod_region, poblacion FROM read_parquet('{P}/cartografia/regiones.parquet')")
reg_pob = dict(zip(reg_pob.cod_region, reg_pob.poblacion))
REGIONES = [{'cod': int(r.cod_region), 'nombre': r.nombre, 'poblacion': int(reg_pob.get(r.cod_region) or 0)} for r in regiones.itertuples()]

tipos = q(f"SELECT coalesce(tipo,'SIN DATO') t, count(*) n FROM {SRC} WHERE {WHERE} GROUP BY 1 ORDER BY n DESC")
TIPOS = list(tipos.t); tipo_idx = {t: i for i, t in enumerate(TIPOS)}
causas = q(f"SELECT coalesce(causa,'SIN DATO') c, count(*) n FROM {SRC} WHERE {WHERE} GROUP BY 1 ORDER BY n DESC")
CAUSAS = list(causas.c); causa_idx = {c: i for i, c in enumerate(CAUSAS)}

comunas = q(f"""SELECT c.cut_com, any_value(c.comuna) nombre, any_value(c.cod_region) cod_region, any_value(c.poblacion) poblacion
    FROM read_parquet('{P}/cartografia/comunas.parquet') c GROUP BY c.cut_com ORDER BY c.cut_com""")
COMUNAS = [{'cut': r.cut_com, 'nombre': r.nombre, 'cod': int(r.cod_region), 'pob': int(r.poblacion or 0)} for r in comunas.itertuples()]
com_idx = {r['cut']: i for i, r in enumerate(COMUNAS)}

# ---------- hechos ----------
def metrics(cols, group, full=True):
    sev = "count(*) s, sum(fallecidos) m, sum(graves) g, sum(menos_graves) mg, sum(leves) l" if full else "count(*) s, sum(fallecidos) m"
    return q(f"SELECT {cols}, {sev} FROM {SRC} WHERE {WHERE} GROUP BY {group}")

# factGeo: comuna x año x modo x zona
fg = metrics(f"cut_com, anio, {MODO} modo, {ZONA} zona", f"cut_com, anio, {MODO}, {ZONA}")
FACT_GEO = [[com_idx[r.cut_com], int(r.anio), int(r.modo), int(r.zona), int(r.s), int(r.m or 0), int(r.g or 0), int(r.mg or 0), int(r.l or 0)]
            for r in fg.itertuples() if r.cut_com in com_idx and pd.notna(r.modo)]

def dim_modo(dim_sql, use_causa=False, use_tipo=False):
    if use_causa: sel = f"cod_region, anio, {MODO} modo, coalesce(causa,'SIN DATO') d"; grp = f"cod_region, anio, {MODO}, coalesce(causa,'SIN DATO')"
    elif use_tipo: sel = f"cod_region, anio, {MODO} modo, coalesce(tipo,'SIN DATO') d"; grp = f"cod_region, anio, {MODO}, coalesce(tipo,'SIN DATO')"
    else: sel = f"cod_region, anio, {MODO} modo, {dim_sql} d"; grp = f"cod_region, anio, {MODO}, {dim_sql}"
    df = metrics(sel, grp, full=False)
    out = []
    for r in df.itertuples():
        if pd.isna(r.modo): continue
        d = r.d
        if use_causa: d = causa_idx.get(r.d, 0)
        elif use_tipo: d = tipo_idx.get(r.d, 0)
        elif pd.isna(d): continue
        out.append([int(r.cod_region), int(r.anio), int(r.modo), int(d), int(r.s), int(r.m or 0)])
    return out

FACT_TIPO = dim_modo(None, use_tipo=True)
FACT_CAUSA = dim_modo(None, use_causa=True)
FACT_MES = dim_modo('mes')
FACT_HORA = dim_modo('hora')
FACT_DIA = dim_modo('dia_semana')

# gridHot: celda ~440 m x comuna x modo (para mapa de calor filtrable por modo)
BIN = 0.004
gh = q(f"""SELECT round(lat/{BIN})*{BIN} la, round(lon/{BIN})*{BIN} lo, cut_com, {MODO} modo, count(*) s, sum(fallecidos) m
    FROM {SRC} WHERE {WHERE} AND lat IS NOT NULL AND lon IS NOT NULL AND lat BETWEEN -56 AND -17 AND lon BETWEEN -110 AND -66
    GROUP BY 1, 2, cut_com, {MODO}""")
GRID_HOT = [[round(r.la, 3), round(r.lo, 3), com_idx[r.cut_com], int(r.modo), int(r.s), int(r.m or 0)]
            for r in gh.itertuples() if r.cut_com in com_idx and pd.notna(r.modo)]

# ---------- GeoJSON ----------
def round_coords(o, nd=3):
    if isinstance(o, list):
        return [round(x, nd) for x in o] if o and isinstance(o[0], (int, float)) else [round_coords(x, nd) for x in o]
    return o
def topo_geojson(path, cols, tol, nd=4):
    """Simplifica preservando bordes compartidos (topología) -> polígonos que calzan, sin huecos."""
    g = gpd.read_parquet(path)[cols + ['geometry']].copy()
    g['geometry'] = g.geometry.buffer(0)
    topo = tp.Topology(g, prequantize=True, toposimplify=tol)
    gj = json.loads(topo.to_geojson())
    for f in gj['features']:
        f.pop('id', None)
        f['geometry']['coordinates'] = round_coords(f['geometry']['coordinates'], nd)
    return gj
GJ_COMUNAS = topo_geojson(f'{P}/cartografia/comunas.parquet', ['cut_com'], 0.005)
GJ_REGIONES = topo_geojson(f'{P}/cartografia/regiones.parquet', ['cod_region'], 0.01)

# ---------- Áreas metropolitanas / conurbaciones (varias comunas a la vez) ----------
import collections as _col
mt = q(f"""SELECT area_metro am, cut_com, count(*) n FROM {SRC}
           WHERE {WHERE} AND area_metro IS NOT NULL AND cut_com IS NOT NULL
           GROUP BY area_metro, cut_com""")
_metros = {}
for r in mt.itertuples():
    if r.cut_com in com_idx:
        _metros.setdefault(r.am, []).append(com_idx[r.cut_com])
METROS = []
for nombre in sorted(_metros):
    coms = sorted(set(_metros[nombre]))
    cod = _col.Counter(COMUNAS[ci]['cod'] for ci in coms).most_common(1)[0][0]
    METROS.append({'nombre': nombre, 'coms': coms, 'cod': int(cod)})
print('  áreas metropolitanas:', [m['nombre'] for m in METROS])

# ---------- Puntos individuales (para hexágonos 3D, contornos KDE y clústeres) ----------
# Compacto: [lat, lon, año-offset, cod_region, modoIdx, tipoIdx, zona, fallecidos]
pts = q(f"""SELECT round(lat,4) la, round(lon,4) lo, anio, cod_region, modo, coalesce(tipo,'SIN DATO') tipo,
                   {ZONA} zona, least(coalesce(fallecidos,0),9) f, cut_com
            FROM {SRC} WHERE {WHERE} AND lat IS NOT NULL AND lon IS NOT NULL
              AND lat BETWEEN -56 AND -17 AND lon BETWEEN -110 AND -66""")
PUNTOS = [[r.la, r.lo, int(r.anio) - ANIO_MIN, int(r.cod_region), modo_idx[r.modo], tipo_idx.get(r.tipo, 0),
           int(r.zona), int(r.f), com_idx.get(r.cut_com, -1)]
          for r in pts.itertuples() if r.modo in modo_idx]
# Los puntos NO se embeben (son ~436k): se escriben por región y se cargan bajo demanda.
_pdir = os.path.join(BASE, 'data', 'puntos'); os.makedirs(_pdir, exist_ok=True)
for _f in os.listdir(_pdir):
    os.remove(os.path.join(_pdir, _f))
_pby = _col.defaultdict(list)
for _pt in PUNTOS:
    _pby[_pt[3]].append(_pt)
for _cod, _arr in _pby.items():
    json.dump(_arr, open(os.path.join(_pdir, f'{_cod}.json'), 'w', encoding='utf-8'), separators=(',', ':'))
PUNTOS_REGIONES = sorted(int(c) for c in _pby)
print('  puntos por región ->', len(_pby), 'archivos en data/puntos/')

# ---------- Red vial segmentada (linear referencing, precómputo offline) ----------
RED_VIAL = None
rvpath = os.path.join(BASE, 'data', 'parquet', 'red_vial_siniestros.parquet')
if os.path.exists(rvpath):
    rv = gpd.read_parquet(rvpath)
    if rv.crs and rv.crs.to_epsg() != 4326:
        rv = rv.to_crs(4326)
    RED_VIAL = []
    for r in rv.itertuples():
        g = r.geometry
        if g is None or g.is_empty:
            continue
        parts = list(g.geoms) if g.geom_type == 'MultiLineString' else [g]
        for ln in parts:
            coords = [[round(x, 4), round(y, 4)] for x, y in ln.coords]
            if len(coords) >= 2:
                RED_VIAL.append([coords, int(r.n), int(r.f), int(r.cod_region)])
    # La red vial tampoco se embebe: por región, bajo demanda.
    _rdir = os.path.join(BASE, 'data', 'redvial'); os.makedirs(_rdir, exist_ok=True)
    for _f in os.listdir(_rdir):
        os.remove(os.path.join(_rdir, _f))
    _rby = _col.defaultdict(list)
    for _seg in RED_VIAL:
        _rby[_seg[3]].append(_seg)
    for _cod, _arr in _rby.items():
        json.dump(_arr, open(os.path.join(_rdir, f'{_cod}.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    print('  red vial por región ->', len(_rby), 'archivos en data/redvial/')

# ---------- FASE 2: personas accidentadas (base persona_vehiculo) ----------
PERS = None
ppath = os.path.join(BASE, 'data', 'parquet', 'personas.parquet')
if os.path.exists(ppath):
    PP = f"read_parquet('{ppath.replace(chr(92), '/')}')"
    PW = "anio IS NOT NULL AND cod_region IS NOT NULL"
    CAT_EDAD = ['Niños', 'Jóvenes', 'Adultos jóvenes', 'Personas mayores', 'No se informa']
    RANGOS = ['0 a 14 años', '15 a 29 años', '30 a 44 años', '45 a 59 años', '60 años y más', 'No se informa']
    pres = set(q(f"SELECT DISTINCT cat_edad FROM {PP}").cat_edad.dropna())
    CAT_EDAD = [c for c in CAT_EDAD if c in pres] + [c for c in pres if c not in CAT_EDAD]
    USUARIOS = list(q(f"SELECT usuario, count(*) n FROM {PP} WHERE {PW} AND usuario IS NOT NULL GROUP BY 1 ORDER BY n DESC").usuario)
    ROLES = list(q(f"SELECT rol, count(*) n FROM {PP} WHERE {PW} AND rol IS NOT NULL GROUP BY 1 ORDER BY n DESC").rol)
    SEXOS = list(q(f"SELECT sexo, count(*) n FROM {PP} WHERE {PW} AND sexo IS NOT NULL GROUP BY 1 ORDER BY n DESC").sexo)
    PANIOS = [int(x) for x in q(f"SELECT DISTINCT anio FROM {PP} WHERE anio IS NOT NULL ORDER BY anio").anio]
    ce_idx = {c: i for i, c in enumerate(CAT_EDAD)}; us_idx = {c: i for i, c in enumerate(USUARIOS)}
    ro_idx = {c: i for i, c in enumerate(ROLES)}; sx_idx = {c: i for i, c in enumerate(SEXOS)}; ra_idx = {c: i for i, c in enumerate(RANGOS)}
    PWC = PW + " AND cut_com IS NOT NULL"   # claveado por comuna (permite filtrar por ciudad); región = comuna.cod
    def pmet(dc):
        return q(f"SELECT cut_com, anio, {dc} d, count(*) n, sum(fallecidos) f FROM {PP} WHERE {PWC} AND {dc} IS NOT NULL GROUP BY cut_com, anio, {dc}")
    def pack(df, idx):
        return [[com_idx[r.cut_com], int(r.anio), idx[r.d], int(r.n), int(r.f or 0)] for r in df.itertuples() if r.cut_com in com_idx and r.d in idx]
    PERS_EDAD = pack(pmet('cat_edad'), ce_idx)          # [comIdx, anio, catEdadIdx, n, f]
    PERS_USUARIO = pack(pmet('usuario'), us_idx)
    PERS_ROL = pack(pmet('rol'), ro_idx)
    pir = q(f"SELECT cut_com, anio, rango_etareo ra, sexo sx, count(*) n FROM {PP} WHERE {PWC} AND rango_etareo IS NOT NULL AND sexo IS NOT NULL GROUP BY cut_com, anio, rango_etareo, sexo")
    PERS_PIR = [[com_idx[r.cut_com], int(r.anio), ra_idx[r.ra], sx_idx[r.sx], int(r.n)] for r in pir.itertuples() if r.cut_com in com_idx and r.ra in ra_idx and r.sx in sx_idx]
    PERS = {'anios': PANIOS, 'catEdad': CAT_EDAD, 'usuarios': USUARIOS, 'roles': ROLES, 'sexos': SEXOS, 'rangos': RANGOS,
            'edad': PERS_EDAD, 'usuario': PERS_USUARIO, 'rol': PERS_ROL, 'piramide': PERS_PIR}
    print(f'  PERSONAS(comuna): edad={len(PERS_EDAD)} usuario={len(PERS_USUARIO)} rol={len(PERS_ROL)} piramide={len(PERS_PIR)} · años {PANIOS[0]}-{PANIOS[-1]}')

DATA = {
    'meta': {
        'generado': BUILD, 'anios': list(range(ANIO_MIN, ANIO_MAX + 1)),
        'fuente': 'CONASET — Base consolidada de siniestros 2020–2025',
        'nota': ('Siniestros georreferenciados 2020–2025 (urbano y rural), base oficial consolidada de CONASET. '
                 'El "modo involucrado" marca si en el siniestro participó un peatón (atropello), una motocicleta o '
                 'una bicicleta; el resto se clasifica como vehículo. Un siniestro se asigna a un solo modo por '
                 'prioridad (peatón > moto > bici > vehículo). Datos referenciales.'),
        'regiones': REGIONES, 'tipos': TIPOS, 'causas': CAUSAS, 'modos': MODOS, 'metros': METROS,
        'zonas': ['Urbana', 'Rural', 'Sin dato'],
        'dias': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
    },
    'comunas': COMUNAS, 'factGeo': FACT_GEO,
    'factTipo': FACT_TIPO, 'factCausa': FACT_CAUSA, 'factMes': FACT_MES, 'factHora': FACT_HORA, 'factDia': FACT_DIA,
    'gridHot': GRID_HOT, 'geoComunas': GJ_COMUNAS, 'geoRegiones': GJ_REGIONES,
    'personas': PERS,
}
DATA['meta']['puntosRegiones'] = PUNTOS_REGIONES
out = os.path.join(BASE, 'data_bundle.js')
with open(out, 'w', encoding='utf-8') as f:
    f.write('/* Generado por procesar_accidentes.py — no editar a mano. */\n')
    f.write('window.DATA = ')
    json.dump(DATA, f, ensure_ascii=False, separators=(',', ':'))
    f.write(';\n')
mb = os.path.getsize(out) / 1e6
print(f'data_bundle.js -> {mb:.2f} MB')
print(f'  factGeo={len(FACT_GEO)} factTipo={len(FACT_TIPO)} factCausa={len(FACT_CAUSA)} factMes={len(FACT_MES)} factHora={len(FACT_HORA)} factDia={len(FACT_DIA)} gridHot={len(GRID_HOT)}')
print(f'  comunas={len(COMUNAS)} regiones={len(REGIONES)} tipos={len(TIPOS)} causas={len(CAUSAS)} modos={len(MODOS)}')
print(f'  puntos={len(PUNTOS)} redVial={len(RED_VIAL) if RED_VIAL else 0}')
con.close()
