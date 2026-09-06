# -*- coding: utf-8 -*-
"""Geocodifica os2_siniestros.parquet (Carabineros O.S.2, sin coordenadas) usando el activo
Red Vial de Chile (SOLO LECTURA):
  - RED DETALLADA nacional (345 comunas, OSM): intersección calle_1×calle_2 por nodo compartido,
    y centroide de la calle cuando hay una sola vía.
  - RED MOP (rol + km): ruta+km por referenciación lineal, anclada a la comuna.

Prioridad por registro:  RUTA+km  →  intersección calle_1×calle_2  →  calle_1 (centroide de vía)
Salida: data/OS2/parquet/os2_siniestros_geo.parquet  (+ lat, lon, geo_calidad, geo_dist_comuna_km)

geo_calidad ∈ {ruta_km, interseccion, calle, ''}.  '' = no geocodificado (con motivo en el conteo).
Todo punto se descarta si cae a > GATE_KM de la comuna declarada (match espurio).
Uso:  python -X utf8 scripts/geocodificar_os2.py [--anios 2024]   (sin --anios = todos)
"""
import os, sys, re, glob, unicodedata, warnings, argparse
warnings.filterwarnings('ignore')
import geopandas as gpd, pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union, nearest_points

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RV = r"C:\Users\Rodrigo\Análisis RMG\Red Vial de Chile"
sys.path.append(os.path.join(RV, 'scripts'))
from geocodificar import normalizar  # misma normalización oficial del activo
SRC = os.path.join(BASE, 'data', 'OS2', 'parquet', 'os2_siniestros.parquet')
OUT = os.path.join(BASE, 'data', 'OS2', 'parquet', 'os2_siniestros_geo.parquet')
RD = os.path.join(RV, 'data', 'processed', 'red_detallada_chile', 'arcos')
CART = os.path.join(BASE, 'data', 'parquet', 'cartografia', 'comunas.parquet')

def nc(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9 ]', ' ', s).strip()

def via(s):
    """Limpia el nombre de vía O.S.2: descarta el tag de tipo tras '=>' (GRECIA => AVDA) y
    se queda con el primer código en listas multi-ruta (R-85, R-89). Devuelve '' si vacío."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ''
    return str(s).split('=>')[0].split(',')[0].strip()

# ---------- comunas (anclaje + validación) ----------
_com = gpd.read_parquet(CART, columns=['cut_com', 'geometry']); _com['cut_com'] = _com['cut_com'].astype(str).str.zfill(5)
CUT2POLY = dict(zip(_com['cut_com'], _com.geometry))
_com32 = _com.to_crs(32719)
CUT2POLY32 = dict(zip(_com32['cut_com'], _com32.geometry))
GATE_KM = 5.0

# ---------- Red detallada nacional (intersección + calle) ----------
# Por región cacheamos los arcos; por comuna cacheamos: nombre->nodos, nombre->geometrías,
# nodo->coordenada (tomada del extremo de la geometría del arco; los nodo_id de arcos NO
# coinciden con la tabla `nodos`, así que la coordenada se saca de los vértices del arco).
_REG = {}
def region_arcos(reg):
    if reg not in _REG:
        f = os.path.join(RD, f'cut_reg={reg}', 'parte.parquet')
        if not os.path.exists(f):
            _REG[reg] = None
        else:
            a = gpd.read_parquet(f, columns=['nombre_ruta', 'rol', 'nodo_a', 'nodo_b', 'cut_com', 'geometry'])
            a['cut_com'] = a['cut_com'].astype(str).str.zfill(5)
            a['_nom'] = a['nombre_ruta'].map(lambda x: normalizar(x) if pd.notna(x) else '')
            _REG[reg] = a
    return _REG[reg]

_COM = {}
def comuna_index(cut):
    if cut not in _COM:
        a = region_arcos(cut[:2])
        if a is None:
            _COM[cut] = None
        else:
            sub = a[a['cut_com'] == cut]
            n2nodes, n2geom, ncoord, rol2geom = {}, {}, {}, {}
            for nom, rol, na, nb, geom in zip(sub['_nom'].values, sub['rol'].values, sub['nodo_a'].values,
                                              sub['nodo_b'].values, sub.geometry.values):
                if nom:
                    st = n2nodes.setdefault(nom, set()); st.add(na); st.add(nb)
                    n2geom.setdefault(nom, []).append(geom)
                    cs = geom.coords
                    ncoord.setdefault(na, cs[0]); ncoord.setdefault(nb, cs[-1])
                if pd.notna(rol):
                    rk = rol_key(rol)[0]
                    if rk: rol2geom.setdefault(rk, []).append(geom)
            _COM[cut] = (n2nodes, n2geom, ncoord, rol2geom)
    return _COM[cut]

def match_names(n2, nombre):
    """Devuelve las claves de nombre que matchean (exacto; si no, por contención en ambos sentidos)."""
    n = normalizar(nombre)
    if not n or not n2: return []
    if n in n2: return [n]
    return [k for k in n2 if n in k or k in n]

def geo_interseccion(cut, c1, c2):
    idx = comuna_index(cut)
    if idx is None: return None, 'sin_red'
    n2nodes, n2geom, ncoord, _ = idx
    a = match_names(n2nodes, c1)
    if not a: return None, 'no_calle1'
    b = match_names(n2nodes, c2)
    if not b: return None, 'no_calle2'
    na = set().union(*[n2nodes[k] for k in a]); nb = set().union(*[n2nodes[k] for k in b])
    common = [nd for nd in (na & nb) if nd in ncoord]
    if common:  # comparten nodo del grafo -> cruce exacto
        xs = [ncoord[nd] for nd in common]
        return Point(sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)), 'interseccion'
    # sin nodo compartido: intersección/cercanía geométrica real de ambas vías (~55 m)
    ga = unary_union([g for k in a for g in n2geom[k]]); gb = unary_union([g for k in b for g in n2geom[k]])
    inter = ga.intersection(gb)
    if not inter.is_empty:
        return inter.centroid, 'interseccion'
    p, q = nearest_points(ga, gb)
    if p.distance(q) <= 0.0006:   # ~55-65 m en latitudes de Chile
        return Point((p.x + q.x) / 2, (p.y + q.y) / 2), 'cercania'
    return None, 'sin_cruce'

def geo_calle(cut, c1):
    idx = comuna_index(cut)
    if idx is None: return None, 'sin_red'
    _, n2geom, _, _ = idx
    a = match_names(n2geom, c1)
    if not a: return None, 'no_calle'
    geoms = [g for k in a for g in n2geom[k]]
    return unary_union(geoms).centroid, 'calle'   # centroide de la vía (menor precisión)

def geo_ruta_rd(cut, nombre):
    """Fallback de ruta sobre la red detallada: cuando MOP no ubica por km, coloca el punto en el
    centroide de los arcos de esa ruta dentro de la comuna. La red detallada trae rutas menores,
    casi siempre por NOMBRE (nombre_ruta) y a veces por rol -> se prueban ambos."""
    idx = comuna_index(cut)
    if idx is None: return None, 'sin_red'
    n2nodes, n2geom, ncoord, rol2geom = idx
    rk = rol_key(nombre)[0]
    if rk and rk in rol2geom:
        return unary_union(rol2geom[rk]).centroid, 'ruta_aprox'
    a = match_names(n2geom, nombre)   # por nombre (Ruta 5 Sur, N-860, Longitudinal...)
    if a:
        geoms = [g for k in a for g in n2geom[k]]
        return unary_union(geoms).centroid, 'ruta_aprox'
    return None, 'rol_no_encontrado'

# ---------- Red MOP (ruta+km) ----------
print('Cargando red MOP...')
DIRS = ('NORTE', 'SUR', 'PONIENTE', 'ORIENTE', 'ESTE', 'OESTE')
def rol_key(s):
    t = nc(s); d = next((x for x in DIRS if re.search(r'\b' + x + r'\b', t)), None)
    t = re.sub(r'\bRUTA\b', '', t)
    for x in DIRS: t = re.sub(r'\b' + x + r'\b', '', t)
    return re.sub(r'[^A-Z0-9]', '', t), d
_mopf = glob.glob(os.path.join(RV, 'data', 'processed', 'red_vial', '**', 'parte.parquet'), recursive=True)
MOP = pd.concat([gpd.read_parquet(f) for f in _mopf], ignore_index=True)
MOP = gpd.GeoDataFrame(MOP, geometry='geometry', crs=4326).to_crs(32719)[['rol', 'nombre_ruta', 'km_i', 'km_f', 'geometry']]
MOP['_k'] = MOP['rol'].map(lambda r: rol_key(r)[0])
MOP['_nom'] = MOP['nombre_ruta'].map(nc)
_combuf = _com32.copy(); _combuf['geometry'] = _com32.buffer(2000)
MOP = gpd.sjoin(MOP, _combuf[['cut_com', 'geometry']], how='left', predicate='intersects').drop(columns='index_right')
MOP_IDX = {k: sub for k, sub in MOP.groupby('_k')}

def geo_ruta(nombre, km, cut):
    """Ruta+km ANCLADA a la comuna: un rol como Ruta 5 recorre todo Chile, así que se restringe a los
    segmentos del rol que pasan por la comuna del siniestro y recién ahí se matchea el km."""
    km = pd.to_numeric(str(km).replace(',', '.'), errors='coerce')
    if pd.isna(km): return None, 'sin_km'
    k, d = rol_key(nombre); sub = MOP_IDX.get(k)
    if sub is None: return None, 'rol_no_encontrado'
    if pd.notna(cut):
        loc = sub[sub['cut_com'] == cut]
        if not len(loc): return None, 'rol_fuera_comuna'
        sub = loc
    if d and sub['_nom'].str.contains(d).any() and (~sub['_nom'].str.contains(d)).any():
        sub = sub[sub['_nom'].str.contains(d)]
    m = float(km) * 1000.0
    seg = sub[(sub['km_i'] <= m) & (sub['km_f'] >= m)]
    if not len(seg):
        i = (sub['km_i'] - m).abs().values.argmin(); r = sub.iloc[i]
        if min(abs(r['km_i'] - m), abs(r['km_f'] - m)) > 3000: return None, 'km_fuera_rango'
        seg = sub.iloc[[i]]
    r = seg.iloc[0]; f = (m - r['km_i']) / max(1.0, (r['km_f'] - r['km_i']))
    return r.geometry.interpolate(max(0, min(1, f)), normalized=True), 'ruta_km'   # 32719

def _geo_one(cut, es_ruta, c1, c2, rt, km):
    if pd.isna(cut): return None, None, None, 'sin_cut'
    if es_ruta:
        nom = c1 if c1 else rt
        p, c = geo_ruta(nom, km, cut); metric = True          # MOP: preciso por km
        if p is None:
            p, c = geo_ruta_rd(cut, nom); metric = False       # red detallada: centroide del rol en comuna
    elif c2:
        p, c = geo_interseccion(cut, c1, c2); metric = False
    elif c1:
        p, c = geo_calle(cut, c1); metric = False
    else:
        return None, None, None, 'sin_via'
    if p is None or p.is_empty: return None, None, None, c
    return p.x, p.y, metric, c

def geocode(df):
    df = df.reset_index(drop=True)
    es_ruta = (df['calle_1'].astype(str).str.upper().str.contains('RUTA', na=False) | df['ruta'].notna())
    q = pd.DataFrame({
        'cut': df['cut_com'].astype('string'), 'es_ruta': es_ruta.values,
        'c1': df['calle_1'].map(via), 'c2': df['calle_2'].map(via),
        'rt': df['ruta'].map(via), 'km': df['km'].astype('string').fillna(''),
    })
    keys = q.drop_duplicates().reset_index(drop=True)
    print(f'  {len(df):,} filas -> {len(keys):,} consultas únicas', flush=True)
    res = {}
    for t in keys.itertuples(index=False):
        res[tuple(t)] = _geo_one(t.cut, t.es_ruta, t.c1, t.c2, t.rt, t.km)
    tuples = list(map(tuple, q.itertuples(index=False, name=None)))
    xs = [res[t][0] for t in tuples]; ys = [res[t][1] for t in tuples]
    ms = [res[t][2] for t in tuples]; cs = [res[t][3] for t in tuples]
    lon = [None] * len(df); lat = [None] * len(df)
    met = [i for i, m in enumerate(ms) if m is True]
    if met:
        gg = gpd.GeoSeries([Point(xs[i], ys[i]) for i in met], crs=32719).to_crs(4326)
        for j, i in enumerate(met): lon[i] = gg.iloc[j].x; lat[i] = gg.iloc[j].y
    for i, m in enumerate(ms):
        if m is False: lon[i] = xs[i]; lat[i] = ys[i]
    cut_arr = df['cut_com'].astype('string').values
    out_lat = [None] * len(df); out_lon = [None] * len(df); out_cal = list(cs); out_d = [None] * len(df)
    have = [i for i in range(len(df)) if lat[i] is not None]
    if have:
        pts = gpd.GeoSeries([Point(lon[i], lat[i]) for i in have], crs=4326).to_crs(32719)
        for j, i in enumerate(have):
            poly = CUT2POLY32.get(cut_arr[i])
            dkm = round(pts.iloc[j].distance(poly) / 1000, 2) if poly is not None else None
            if dkm is not None and dkm > GATE_KM:
                out_cal[i] = 'fuera_comuna'
            else:
                out_lat[i] = round(lat[i], 6); out_lon[i] = round(lon[i], 6); out_d[i] = dkm
    df = df.copy()
    df['lat'] = out_lat; df['lon'] = out_lon; df['geo_calidad'] = out_cal; df['geo_dist_comuna_km'] = out_d
    return df

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--anios', type=int, nargs='*'); ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    df = pd.read_parquet(SRC)
    if a.anios: df = df[df['anio'].isin(a.anios)].copy()
    print(f'Geocodificando {len(df):,} siniestros...', flush=True)
    out = geocode(df)
    ok = out['lat'].notna()
    print(f'\n=== geocodificados: {int(ok.sum()):,} ({100*ok.mean():.0f}%) ===')
    print(out['geo_calidad'].value_counts().to_string())
    val = out[ok & out['geo_dist_comuna_km'].notna()]
    if len(val): print(f"\nvalidación: {100*(val['geo_dist_comuna_km']<1).mean():.0f}% caen a <1 km de su comuna")
    out.to_parquet(a.out, compression='zstd', index=False)
    print(f'-> {a.out}')
