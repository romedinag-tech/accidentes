# -*- coding: utf-8 -*-
"""
Convierte todos los shapefiles descargados (CONASET + cartografía base) a GeoParquet,
formato columnar comprimido, ideal para análisis rápido con DuckDB / pandas / geopandas.

- Nombres de campo corregidos (encoding ISO-8859-1) y normalizados a snake_case ASCII.
- Valores de texto reparados (ñ) y acentos.
- Se agregan columnas CANÓNICAS homogéneas (region, comuna, tipo, causa, severidad, lat, lon...)
  presentes en TODAS las filas, independientes de la "era" de esquema de cada capa.
- Se conservan además TODAS las columnas originales (sin pérdida).
- Metadatos de procedencia: tema, capa_origen, anio_archivo, region_archivo, nivel.
- Geometría en EPSG:4326 (WGS84).

Salida: data/parquet/<tema>.parquet  y  data/parquet/cartografia/<capa>.parquet
"""
import os, re, glob, unicodedata, warnings, json
import pyogrio, geopandas as gpd, pandas as pd
from shapely import points
import ftfy

warnings.filterwarnings('ignore')
pyogrio.set_gdal_config_options({'SHAPE_ENCODING': 'ISO-8859-1'})  # corrige nombres de campo

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'data', 'CONASET')
OUT = os.path.join(BASE, 'data', 'parquet')
CARTO_OUT = os.path.join(OUT, 'cartografia')
os.makedirs(CARTO_OUT, exist_ok=True)

THEMES = {
    '01_Puntos_criticos':          ('puntos_criticos',        'Puntos críticos'),
    '02_Atropellos':               ('atropellos',             'Atropellos'),
    '03_Siniestros_individuales':  ('siniestros_individuales','Siniestros individuales'),
    '04_Siniestros_en_ruta':       ('siniestros_en_ruta',     'Siniestros en ruta'),
    '05_Motocicletas':             ('motocicletas',           'Motocicletas'),
    '06_Bicicletas':               ('bicicletas',             'Bicicletas'),
    '07_Siniestros_urbanos':       ('siniestros_urbanos',     'Siniestros urbanos'),
    '08_Region_multianual':        ('region_multianual',      'Región multianual'),
}

REGIONS = ['Arica','Parinacota','Tarapaca','Antofagasta','Atacama','Coquimbo','Valparaiso',
           'Metropolitana','OHiggins','Ohiggins','Maule','Nuble','Biobio','Bio_Bio','Araucania',
           'Los_Rios','Los Rios','Los_Lagos','Los Lagos','Aysen','Magallanes','Concepcion','Santiago']

def clean_name(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    return s or 'col'

def dedupe(cols):
    seen, out = {}, []
    for c in cols:
        if c in seen:
            seen[c] += 1; out.append(f'{c}__{seen[c]}')
        else:
            seen[c] = 1; out.append(c)
    return out

def sanitize_for_arrow(df):
    """Evita tipos mixtos: columnas object -> numérico si se puede, si no texto (NaN preservado).
    Los códigos CUT se mantienen SIEMPRE como texto (conservan ceros a la izquierda)."""
    for c in df.columns:
        if c == 'geometry' or df[c].dtype != object:
            continue
        if c.startswith('cut_') or c in ('cut_com', 'cut_reg', 'cut_prov'):
            df[c] = df[c].map(lambda v: None if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v))
            continue
        num = pd.to_numeric(df[c], errors='coerce')
        if num.notna().sum() >= df[c].notna().sum() * 0.95:  # casi todo numérico
            df[c] = num
        else:
            df[c] = df[c].map(lambda v: None if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v))
    return df

def repair(v):
    """Corrige mojibake (doble-codificación UTF-8 leída como latin1) con ftfy. Idempotente."""
    if not isinstance(v, str):
        return v
    return ftfy.fix_text(v).strip()

# ---- Normalización de región a catálogo canónico (código CUT + nombre) ----
REG_CAT = [
    (('ARICA', 'PARINACOTA'), 15, 'Arica y Parinacota'),
    (('TARAPACA',),            1, 'Tarapacá'),
    (('ANTOFAGASTA',),         2, 'Antofagasta'),
    (('ATACAMA',),             3, 'Atacama'),
    (('COQUIMBO',),            4, 'Coquimbo'),
    (('VALPARA',),             5, 'Valparaíso'),
    (('METROPOLITANA', 'SANTIAGO'), 13, 'Metropolitana de Santiago'),
    (('OHIGGINS', 'O HIGGINS', 'LIBERTADOR'), 6, "Libertador General Bernardo O'Higgins"),
    (('MAULE',),               7, 'Maule'),
    (('UBLE',),               16, 'Ñuble'),
    (('BIOB', 'BIO BIO'),      8, 'Biobío'),
    (('ARAUCAN',),             9, 'La Araucanía'),
    (('LOS RIOS', 'LOSRIOS'), 14, 'Los Ríos'),
    (('LAGOS',),              10, 'Los Lagos'),
    (('AYSEN',),              11, 'Aysén'),
    (('MAGALLANES',),         12, 'Magallanes y de la Antártica Chilena'),
]

def norm_region(raw):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return (None, None)
    s = ftfy.fix_text(str(raw)).upper()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Z ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    for kws, cod, nombre in REG_CAT:
        if any(kw in s for kw in kws):
            return (cod, nombre)
    return (None, None)

# canonical -> lista ordenada de nombres (ya cleaned) candidatos
CANON = {
    'id_accidente': ['idaccident', 'idaccidente'],
    'fecha':        ['fecha'],
    'anio':         ['ano', 'anio'],
    'mes':          ['mes'],
    'dia_mes':      ['dia_mes', 'diames'],
    'dia_semana':   ['dia_semana', 'diasemana'],
    'hora':         ['hora'],
    'region':       ['region', 'region_dpa'],
    'provincia':    ['provincia'],
    'comuna':       ['comuna', 'comuna_dpa', 'comuna1', 'comuna2'],
    'cut_reg':      ['cut_reg'],
    'cut_prov':     ['cut_prov'],
    'cut_com':      ['cut_com'],
    'ciudad':       ['ciudad'],
    'zona':         ['zona'],
    'tipo':         ['tipo_accid', 'tipoaccide', 'claseaccid'],
    'tipo_conaset': ['tipo_cona', 'tipo_conas'],
    'causa':        ['causa_acci', 'causa_cara', 'causa'],
    'causa_conaset':['causa_con', 'causa_cona'],
    'ubicacion':    ['ubicacion', 'ubicacionr', 'ubicaci_1'],
    'calle_1':      ['calle_uno', 'callevia1'],
    'calle_2':      ['calle_dos', 'callevia2'],
    'numero':       ['numero', 'frentenume'],
    'ruta':         ['ruta'],
    'fallecidos':   ['fallecidos', 'muerto', 'muertos_1'],
    'graves':       ['graves', 'grave', 'graves_1'],
    'menos_graves': ['menos_grav', 'menosgrav'],
    'leves':        ['leves', 'leve', 'leves_1'],
    'lesionados':   ['lesionados'],
    'n_accidentes': ['accidentes', 'cantidad_d'],
    'lat':          ['lat', 'latitud'],
    'lon':          ['lon', 'longitud', 'lng'],
}
NUM_CANON = {'anio','mes','dia_mes','dia_semana','hora','fallecidos','graves','menos_graves',
             'leves','lesionados','n_accidentes','lat','lon'}

def norm_zona(v):
    if not isinstance(v, str):
        return None
    u = v.strip().upper()
    if u.startswith('URB'):
        return 'URBANA'
    if u.startswith('RUR'):
        return 'RURAL'
    return None

def comuna_key(name):
    s = ftfy.fix_text(str(name)).upper()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Z0-9]', '', s)

def norm_cut_com(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).split('.')[0].strip()
    return s.zfill(5) if s.isdigit() and s not in ('0', '00000') else None

_COMUNA_LOOKUP = None
def get_comuna_lookup():
    """(cod_region, nombre_normalizado) -> cut_com, desde el catálogo DPA oficial."""
    global _COMUNA_LOOKUP
    if _COMUNA_LOOKUP is None:
        z = os.path.join(BASE, 'data', 'Cartografia_base', 'Comunas_DPA_Censo2017.zip')
        g = gpd.read_file(f'zip://{os.path.abspath(z)}')
        g.columns = [c if c == 'geometry' else clean_name(ftfy.fix_text(c)) for c in g.columns]
        d = {}
        for _, row in g.iterrows():
            cut = norm_cut_com(row['comuna'])         # 'comuna' = código CUT en esta capa
            if cut:
                d[(int(cut[:2]), comuna_key(row['nom_comuna']))] = cut
        _COMUNA_LOOKUP = d
    return _COMUNA_LOOKUP

def parse_meta(fname):
    yrs = re.findall(r'(20\d\d)', fname)
    anio = int(yrs[-1]) if yrs else None
    fl = fname.lower()
    nivel = 'nacional' if re.search(r'siniestros_individuales_20\d\d(?!\d)', fl) and 'region' not in fl else 'regional'
    reg = None
    for r in REGIONS:
        if r.lower() in fl:
            reg = r.replace('_', ' '); break
    return anio, nivel, reg

def load_layer(zip_path, theme_code, theme_name):
    gdf = gpd.read_file(f'zip://{os.path.abspath(zip_path)}')
    # limpiar nombres (ftfy corrige mojibake en el nombre) + deduplicar
    gdf.columns = dedupe([c if c == 'geometry' else clean_name(ftfy.fix_text(c)) for c in gdf.columns])
    # reparar texto en columnas object
    for c in gdf.columns:
        if c != 'geometry' and gdf[c].dtype == object:
            gdf[c] = gdf[c].map(repair)
    # CRS -> 4326
    try:
        if gdf.crs is None:
            gdf.set_crs(4326, inplace=True)
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(4326)
    except Exception:
        gdf.set_crs(4326, inplace=True, allow_override=True)
    cols = set(gdf.columns)
    canon = {}
    for target, cands in CANON.items():
        for cand in cands:
            if cand in cols:
                canon[target] = gdf[cand]; break
    out = pd.DataFrame(index=gdf.index)
    for target in CANON:
        out['k_' + target] = canon.get(target, pd.Series([None]*len(gdf), index=gdf.index))
    # lat/lon desde geometría si faltan
    geom = gdf.geometry
    if out['k_lat'].isna().all():
        out['k_lat'] = geom.y
    if out['k_lon'].isna().all():
        out['k_lon'] = geom.x
    # tipos numéricos
    for t in NUM_CANON:
        out['k_'+t] = pd.to_numeric(out['k_'+t], errors='coerce')
    # fecha
    out['k_fecha'] = pd.to_datetime(out['k_fecha'], errors='coerce', utc=True)
    # anio robusto: fecha si cae en rango válido [2014,2024]; si no, año del archivo; si no, col año
    anio_arch = parse_meta(os.path.splitext(os.path.basename(zip_path))[0])[0]
    af = out['k_fecha'].dt.year
    af = af.where((af >= 2014) & (af <= 2024))   # descarta fechas erróneas (1899, 2029, etc.)
    anio = af
    if anio_arch:
        anio = anio.fillna(anio_arch)
    anio = anio.fillna(out['k_anio'])
    out['k_anio'] = anio.astype('Int64')
    # hora correcta (0-23): de hora_aprox (entero) o de la hora tipo tiempo
    cols_all = set(gdf.columns)
    h = None
    if 'hora_aprox' in cols_all:
        h = pd.to_numeric(gdf['hora_aprox'], errors='coerce')
    if 'hora' in cols_all:
        ht = pd.to_datetime(gdf['hora'], errors='coerce', utc=True).dt.hour
        h = ht if h is None else h.fillna(ht)
    out['k_hora'] = (h.where((h >= 0) & (h <= 23)) if h is not None
                     else pd.Series([None] * len(gdf), index=gdf.index)).astype('Int64')
    # mes y día de semana: derivados de fecha (consistente y confiable), 1=Lunes..7=Domingo
    out['k_mes'] = out['k_fecha'].dt.month.astype('Int64')
    out['k_dia_semana'] = (out['k_fecha'].dt.dayofweek + 1).astype('Int64')
    # zona normalizada (URBANO/URBANA -> URBANA)
    out['k_zona'] = out['k_zona'].map(norm_zona)
    # región normalizada (catálogo canónico + código CUT)
    reg_src = out['k_region']
    mp = {v: norm_region(v) for v in reg_src.dropna().unique()}
    out['k_cod_region'] = reg_src.map(lambda v: mp.get(v, (None, None))[0]).astype('Int64')
    out['k_region_norm'] = reg_src.map(lambda v: mp.get(v, (None, None))[1])
    # tipo / causa coalescidos (prioriza clasificación CONASET)
    out['k_tipo_final'] = out['k_tipo_conaset'].where(out['k_tipo_conaset'].notna(), out['k_tipo'])
    out['k_causa_final'] = out['k_causa_conaset'].where(out['k_causa_conaset'].notna(), out['k_causa'])
    # geometría canónica desde lat/lon cuando existan (más confiable)
    ok = out['k_lat'].notna() & out['k_lon'].notna()
    new_geom = geom.copy()
    if ok.any():
        pts = gpd.GeoSeries(points(out.loc[ok,'k_lon'].values, out.loc[ok,'k_lat'].values), crs=4326, index=out[ok].index)
        new_geom.loc[ok] = pts
    # ensamblar: canónicas + originales + metadatos + geom
    fname = os.path.splitext(os.path.basename(zip_path))[0]
    anio, nivel, reg = parse_meta(fname)
    orig = gdf.drop(columns=['geometry'])
    orig.columns = ['o_' + c for c in orig.columns]
    res = pd.concat([out, orig], axis=1)
    res['tema'] = theme_name
    res['capa_origen'] = fname
    res['anio_archivo'] = anio
    res['region_archivo'] = reg
    res['nivel'] = nivel
    res = gpd.GeoDataFrame(res, geometry=new_geom, crs=4326)
    return res

def convert_theme(theme_code):
    slug, name = THEMES[theme_code]
    zips = sorted(glob.glob(os.path.join(SRC, theme_code, '*.zip')))
    parts, rows = [], 0
    for z in zips:
        try:
            g = load_layer(z, theme_code, name)
            parts.append(g); rows += len(g)
        except Exception as e:
            print(f'   ! ERROR {os.path.basename(z)}: {e}')
    gdf = pd.concat(parts, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=4326)
    # renombrar columnas canónicas quitando prefijo k_
    ren = {c: c[2:] for c in gdf.columns if c.startswith('k_')}
    gdf = gdf.rename(columns=ren)
    # normalizar cut_com y rellenar desde nombre de comuna (catálogo DPA) donde falte
    gdf['cut_com'] = gdf['cut_com'].map(norm_cut_com)
    lu = get_comuna_lookup()
    need = gdf['cut_com'].isna() & gdf['comuna'].notna() & gdf['cod_region'].notna()
    if need.any():
        sub = gdf.loc[need]
        keys = zip(sub['cod_region'].astype('Int64').astype(str), sub['comuna'])
        gdf.loc[need, 'cut_com'] = [lu.get((int(cod), comuna_key(nom))) if cod != '<NA>' else None
                                    for cod, nom in keys]
    # fallback de cod_region y region_norm desde el CUT comunal
    m = gdf['cod_region'].isna() & gdf['cut_com'].notna()
    if m.any():
        gdf.loc[m, 'cod_region'] = pd.to_numeric(gdf.loc[m, 'cut_com'].str[:2], errors='coerce').astype('Int64')
    m2 = gdf['region_norm'].isna() & gdf['cod_region'].notna()
    if m2.any():
        gdf.loc[m2, 'region_norm'] = gdf.loc[m2, 'cod_region'].map(COD2NOMBRE)
    geom = gdf.geometry
    gdf = gpd.GeoDataFrame(sanitize_for_arrow(pd.DataFrame(gdf.drop(columns='geometry'))), geometry=geom, crs=4326)
    path = os.path.join(OUT, slug + '.parquet')
    gdf.to_parquet(path, compression='zstd', index=False)
    mb = os.path.getsize(path)/1e6
    print(f'  {slug:26s} capas={len(zips):3d}  filas={rows:7d}  -> {mb:6.2f} MB')
    return dict(tema=name, slug=slug, capas=len(zips), filas=rows, mb=round(mb,2))

COD2NOMBRE = {cod: nombre for _, cod, nombre in REG_CAT}

def _read_carto(fname):
    # Los archivos de cartografía (DPA Esri, OCUC) son UTF-8; leerlos así (no como los shapefiles
    # CONASET que son latin1). ftfy queda como red de seguridad para cualquier residuo.
    pyogrio.set_gdal_config_options({'SHAPE_ENCODING': 'UTF-8'})
    z = os.path.join(BASE, 'data', 'Cartografia_base', fname)
    g = gpd.read_file(f'zip://{os.path.abspath(z)}')
    g.columns = dedupe([c if c == 'geometry' else clean_name(ftfy.fix_text(c)) for c in g.columns])
    for c in g.columns:
        if c != 'geometry' and g[c].dtype == object:
            g[c] = g[c].map(repair)
    return g

def _write_carto(g, slug, out):
    geom = g.geometry
    g = gpd.GeoDataFrame(sanitize_for_arrow(pd.DataFrame(g.drop(columns='geometry'))), geometry=geom, crs=4326)
    path = os.path.join(CARTO_OUT, slug + '.parquet')
    g.to_parquet(path, compression='zstd', index=False)
    mb = os.path.getsize(path)/1e6
    print(f'  {slug:12s} filas={len(g):6d}  cols={len(g.columns)}  -> {mb:6.2f} MB')
    out.append(dict(slug=slug, filas=len(g), mb=round(mb, 2), cols=list(g.columns)))

def _to4326(g):
    if g.crs and g.crs.to_epsg() != 4326:
        g = g.to_crs(4326)
    return g

def convert_carto():
    print('\n== Cartografía base (DPA Censal - Esri Chile / Censo 2017, 16 regiones) ==')
    out = []
    # --- Comunas (345, polígonos, con población) ---
    c = _read_carto('Comunas_DPA_Censo2017.zip')
    c = c.rename(columns={'comuna': 'cut_com', 'nom_comuna': 'comuna', 'region': 'cod_region',
                          'nom_region': 'region_nombre', 'provincia': 'cut_prov', 'nom_provin': 'provincia',
                          't_pob': 'poblacion', 't_hom': 'pob_hombres', 't_muj': 'pob_mujeres',
                          't_viv': 'viviendas', 'superficie': 'superficie_km2', 'densidad': 'densidad_hab_km2'})
    c['cut_com'] = c['cut_com'].astype(str).str.split('.').str[0].str.zfill(5)
    c['cut_prov'] = c['cut_prov'].astype(str).str.split('.').str[0].str.zfill(3)
    c['cod_region'] = pd.to_numeric(c['cod_region'], errors='coerce').astype('Int64')
    c['region_norm'] = c['cod_region'].map(COD2NOMBRE)
    keep = ['cut_com', 'comuna', 'cut_prov', 'provincia', 'cod_region', 'region_norm', 'region_nombre',
            'poblacion', 'pob_hombres', 'pob_mujeres', 'viviendas', 'superficie_km2', 'densidad_hab_km2']
    c = _to4326(c[[k for k in keep if k in c.columns] + ['geometry']])
    _write_carto(c, 'comunas', out)
    # --- Regiones (16, polígonos, con población) ---
    r = _read_carto('Regiones_DPA_Censo2017.zip')
    r = r.rename(columns={'region': 'cod_region', 'nom_region': 'region_nombre',
                          't_pob': 'poblacion', 'superficie': 'superficie_km2', 'densidad': 'densidad_hab_km2'})
    r['cod_region'] = pd.to_numeric(r['cod_region'], errors='coerce').astype('Int64')
    r['region_norm'] = r['cod_region'].map(COD2NOMBRE)
    keep_r = ['cod_region', 'region_norm', 'region_nombre', 'poblacion', 'superficie_km2', 'densidad_hab_km2']
    r = _to4326(r[[k for k in keep_r if k in r.columns] + ['geometry']])
    _write_carto(r, 'regiones', out)
    # --- Provincias (56, polígonos) ---
    p = _read_carto('Provincias_DPA_Censo2017.zip')
    p = p.rename(columns={'provincia': 'cut_prov', 'nom_provin': 'provincia', 'region': 'cod_region',
                          'nom_region': 'region_nombre', 't_pob': 'poblacion'})
    if 'cut_prov' in p.columns:
        p['cut_prov'] = p['cut_prov'].astype(str).str.split('.').str[0].str.zfill(3)
    p['cod_region'] = pd.to_numeric(p.get('cod_region'), errors='coerce').astype('Int64')
    p = _to4326(p)
    _write_carto(p, 'provincias', out)
    # --- Red vial nacional (líneas) ---
    rv = _to4326(_read_carto('Red_Vial_Nacional_Chile.zip'))
    _write_carto(rv, 'red_vial', out)
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    print('== Convirtiendo capas CONASET a GeoParquet ==')
    summary = [convert_theme(tc) for tc in THEMES]
    carto = convert_carto()
    tot = sum(s['mb'] for s in summary) + sum(c['mb'] for c in carto)
    filas = sum(s['filas'] for s in summary)
    print(f'\nTOTAL: {filas} filas de siniestros · {tot:.1f} MB en parquet')
    json.dump({'temas': summary, 'cartografia': carto}, open(os.path.join(OUT,'_resumen.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
