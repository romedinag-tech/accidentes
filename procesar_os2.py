# -*- coding: utf-8 -*-
"""Genera os2_bundle.js (window.OS2) para la ventana O.S.2 (histórico 2010-2025) del dashboard.

Fuente: Carabineros O.S.2 (data/OS2/parquet, ver data/OS2/FUENTE.md). Universo DISTINTO de CONASET
(no mezclar). Pre-agrega en fact-tables compactas por comuna×año, normalizando las categorías (los
años viejos vienen en MAYÚSCULA y desglosadas; se colapsan a canónicas). Ejes:
  serie 2010-2025 · modo · urbano/rural · severidad por modo · causa detallada · tipo de vehículo +
  fuga · edad/sexo (pirámide) · usuario (conductor/pasajero/peatón) · ranking de ciudades normalizado
  por población · densidad geocodificada (hex H3) por región (lazy).

NO identifica al causante (la fuente no marca culpa): las demográficas de conductor son "conductores
involucrados", no "causantes". El 78% geocodificado se agrega a hexágono (nunca puntos individuales).
"""
import os, re, json, unicodedata, datetime, warnings
import pandas as pd
warnings.filterwarnings('ignore')
try:
    import h3
except Exception:
    h3 = None

BASE = os.path.dirname(os.path.abspath(__file__))
OS2 = os.path.join(BASE, 'data', 'OS2', 'parquet')
CARTP = os.path.join(BASE, 'data', 'parquet', 'cartografia')
PUB = os.path.join(BASE, 'data', 'os2hex')       # JSONs lazy por región (densidad) — NO usar 'data/os2'
# (en Windows case-insensitive colisiona con 'data/OS2/' que está gitignored y no se publicaría en Pages)
os.makedirs(PUB, exist_ok=True)
ANIO_MIN, ANIO_MAX = 2010, 2025
BUILD = datetime.date.today().isoformat()

def nc(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9 /]', ' ', s).strip()

# ---------- normalización de categorías ----------
def norm_tipo(t):
    u = nc(t)
    if u.startswith('COLISION'): return 'Colisión'
    if u.startswith('CHOQUE'): return 'Choque'
    if 'ATROPELLO' in u: return 'Atropello'
    if 'VOLCA' in u: return 'Volcadura'
    if u.startswith('CAIDA') or 'CAIDA' in u: return 'Caída'
    return 'Otros'

def norm_sector(s):
    u = nc(s)
    if u.startswith('URB'): return 'Urbano'
    if u.startswith('RUR'): return 'Rural'
    return None

_CAUSA = [
    ('ALCOHOL', 'Alcohol / ebriedad'), ('EBRIEDAD', 'Alcohol / ebriedad'),
    ('NO ATENTO', 'Conducción no atenta'),
    ('DISTANCIA', 'No mantener distancia'),
    ('PERDIDA CONTROL', 'Pérdida de control'), ('PERDIDA DE CONTROL', 'Pérdida de control'),
    ('LUZ ROJA', 'Desobedecer señalización'), ('SEÑAL PARE', 'Desobedecer señalización'),
    ('CEDA EL PASO', 'Desobedecer señalización'), ('SEÑALIZACION', 'Desobedecer señalización'),
    ('DESOBEDECER', 'Desobedecer señalización'),
    ('VELOCIDAD', 'Velocidad imprudente'),
    ('PEATON', 'Imprudencia del peatón'),
    ('ADELANTAMIENTO', 'Adelantamiento indebido'),
    ('FALLAS MECANICAS', 'Fallas mecánicas'), ('FALLA MECANICA', 'Fallas mecánicas'),
    ('DERECHO PREFERENTE', 'No respetar preferencia'),
    ('VIRAJE', 'Virajes indebidos'),
    ('RETROCESO', 'Vehículo en retroceso'),
    ('CONTRA SENTIDO', 'Contra el sentido'), ('IZQUIERDA EJE', 'Contra el sentido'),
    ('CANSANCIO', 'Condición física deficiente'), ('SUEÑO', 'Condición física deficiente'),
    ('ANIMAL', 'Animales en la vía'),
    ('CARGA', 'Problema con la carga'),
    ('DELICTUAL', 'Hecho delictual'),
    ('NO DETERMINAD', 'No determinada'), ('OTRAS CAUSAS', 'Otras'), ('OTRA CAUSA', 'Otras'),
]
def norm_causa(c):
    if c is None or (isinstance(c, float) and pd.isna(c)): return 'No determinada'
    u = nc(c)
    for key, fam in _CAUSA:
        if key in u: return fam
    return 'Otras'

def modo_veh(t):
    u = nc(t)
    if 'BICICLETA' in u or 'PATINETA' in u or 'TRACCION HUMANA' in u: return 'Bicicleta'
    if 'MOTO' in u or 'SCOOTER' in u or 'PATIN MOTORIZADO' in u or 'BICIMOTO' in u or 'ARENERA' in u: return 'Motocicleta'
    if 'BUS' in u or 'TROLEBUS' in u: return 'Bus'
    if 'CAMIONETA' in u: return 'Camioneta'
    if 'CAMION' in u or 'TRACTO' in u or 'REMOLQUE' in u: return 'Camión'
    if 'AUTOMOVIL' in u or 'JEEP' in u or 'STATION' in u or 'FURGON' in u: return 'Automóvil'
    if 'DADO A LA FUGA' in u: return None      # se cuenta como fuga, no como modo
    return 'Otro'

def norm_result(r):
    u = nc(r)
    if 'FALLEC' in u or u == 'MUERTO': return 'Fallecido'
    if u == 'GRAVE': return 'Grave'
    if 'MENOS' in u: return 'Menos grave'
    if u == 'LEVE': return 'Leve'
    if u == 'ILESO': return 'Ileso'
    return None

EDAD_BR = ['0-14', '15-24', '25-34', '35-44', '45-54', '55-64', '65-74', '75+']
def edad_br(e):
    if pd.isna(e) or e < 0 or e > 110: return None
    e = int(e)
    if e < 15: return '0-14'
    if e >= 75: return '75+'
    return EDAD_BR[min(7, 1 + (e - 15) // 10)]

# ---------- cartografía + ciudades (conurbaciones canónicas) ----------
carto = pd.read_parquet(os.path.join(CARTP, 'comunas.parquet'), columns=['cut_com', 'comuna', 'cod_region', 'poblacion'])
carto['cut_com'] = carto['cut_com'].astype(str).str.zfill(5)
COMUNAS = [{'cut': r.cut_com, 'nombre': r.comuna, 'cod': int(r.cod_region), 'pob': int(r.poblacion or 0)}
           for r in carto.itertuples()]
com_idx = {c['cut']: i for i, c in enumerate(COMUNAS)}
reg = pd.read_parquet(os.path.join(CARTP, 'regiones.parquet'), columns=['cod_region', 'poblacion'])
regnom = carto.groupby('cod_region')['comuna'].size()  # placeholder
REG_NOMBRE = {1:'Tarapacá',2:'Antofagasta',3:'Atacama',4:'Coquimbo',5:'Valparaíso',6:"O'Higgins",
              7:'Maule',8:'Biobío',9:'La Araucanía',10:'Los Lagos',11:'Aysén',12:'Magallanes',
              13:'Metropolitana',14:'Los Ríos',15:'Arica y Parinacota',16:'Ñuble'}
REGIONES = [{'cod': int(r.cod_region), 'nombre': REG_NOMBRE.get(int(r.cod_region), str(r.cod_region)),
             'pob': int(r.poblacion or 0)} for r in reg.itertuples()]

_METROS = [
    ('Gran Santiago', ['13101','13102','13103','13104','13105','13106','13107','13108','13109','13110',
                       '13111','13112','13113','13114','13115','13116','13117','13118','13119','13120',
                       '13121','13122','13123','13124','13125','13126','13127','13128','13129','13130',
                       '13131','13132','13201','13401','13403','13604']),
    ('Gran Valparaíso', ['05101','05103','05109','05801','05804']),
    ('Gran Concepción', ['08101','08102','08103','08104','08105','08106','08107','08108','08109','08110','08111','08112']),
    ('Coquimbo–La Serena', ['04101','04102']),
    ('Rancagua–Machalí', ['06101','06115']),
    ('Puerto Montt–Puerto Varas', ['10101','10109','10107']),
    ('Iquique–Alto Hospicio', ['01101','01107']),
]
CIUDADES = []
_pob = {c['cut']: c['pob'] for c in COMUNAS}
for nombre, cuts in _METROS:
    cuts = [c for c in cuts if c in com_idx]
    CIUDADES.append({'nombre': nombre, 'cuts': cuts, 'pob': sum(_pob.get(c, 0) for c in cuts)})

# ---------- siniestros ----------
print('Cargando siniestros O.S.2...')
S = pd.read_parquet(os.path.join(OS2, 'os2_siniestros_geo.parquet'))
S = S[S['anio'].between(ANIO_MIN, ANIO_MAX)].copy()
S['cut_com'] = S['cut_com'].astype('string')
S['tipoN'] = S['tipo'].map(norm_tipo)
S['sectorN'] = S['sector'].map(norm_sector)
S['causaN'] = S['causa'].map(norm_causa)
for c in ['fallecidos', 'graves', 'menos_graves', 'leves']:
    S[c] = pd.to_numeric(S[c], errors='coerce').fillna(0).astype(int)
S['lesionados'] = S['graves'] + S['menos_graves'] + S['leves']
Sv = S[S['cut_com'].isin(com_idx.keys())].copy()

TIPOS = ['Colisión', 'Choque', 'Atropello', 'Volcadura', 'Caída', 'Otros']
SECTORES = ['Urbano', 'Rural']
CAUSAS = list(pd.Series([f for _, f in _CAUSA] + ['Otras']).drop_duplicates())
ti_idx = {t: i for i, t in enumerate(TIPOS)}; se_idx = {s: i for i, s in enumerate(SECTORES)}
ca_idx = {c: i for i, c in enumerate(CAUSAS)}

def A(df, keys, agg):
    g = df.groupby(keys, dropna=True).agg(**agg).reset_index()
    return g

# factSin: [comIdx, anio, sectorIdx, tipoIdx, n, fall, grav, les]
g = A(Sv[Sv['sectorN'].notna()], ['cut_com', 'anio', 'sectorN', 'tipoN'],
      {'n': ('id_accidente', 'size'), 'f': ('fallecidos', 'sum'), 'gr': ('graves', 'sum'), 'le': ('lesionados', 'sum')})
FACT_SIN = [[com_idx[r.cut_com], int(r.anio), se_idx[r.sectorN], ti_idx[r.tipoN],
             int(r.n), int(r.f), int(r.gr), int(r.le)] for r in g.itertuples()]
# factCausa: [comIdx, anio, causaIdx, n, fall]
g = A(Sv, ['cut_com', 'anio', 'causaN'], {'n': ('id_accidente', 'size'), 'f': ('fallecidos', 'sum')})
FACT_CAUSA = [[com_idx[r.cut_com], int(r.anio), ca_idx[r.causaN], int(r.n), int(r.f)] for r in g.itertuples()]

print(f'  siniestros validos: {len(Sv):,} · factSin={len(FACT_SIN)} factCausa={len(FACT_CAUSA)}')

# ---------- vehículos: modo + fuga ----------
print('Cargando vehículos O.S.2...')
V = pd.read_parquet(os.path.join(OS2, 'os2_vehiculos.parquet'), columns=['id_accidente', 'anio', 'cut_com', 'tipo', 'servicio'])
V = V[V['anio'].between(ANIO_MIN, ANIO_MAX)].copy()
V['cut_com'] = V['cut_com'].astype('string')
V['modo'] = V['tipo'].map(modo_veh)
V['fuga'] = (V['tipo'].map(nc).str.contains('DADO A LA FUGA') | V['servicio'].map(nc).str.contains('DADO A LA FUGA'))
MODOS = ['Automóvil', 'Camioneta', 'Motocicleta', 'Bicicleta', 'Bus', 'Camión', 'Otro']
mo_idx = {m: i for i, m in enumerate(MODOS)}
Vv = V[V['cut_com'].isin(com_idx.keys())].copy()
# factVeh: [comIdx, anio, modoIdx, n]  (n = vehículos de ese modo)
g = A(Vv[Vv['modo'].notna()], ['cut_com', 'anio', 'modo'], {'n': ('id_accidente', 'size')})
FACT_VEH = [[com_idx[r.cut_com], int(r.anio), mo_idx[r.modo], int(r.n)] for r in g.itertuples()]

# modo POR SINIESTRO (para severidad por modo): un siniestro cuenta en cada modo involucrado
sev = Sv[['id_accidente', 'anio', 'cut_com', 'fallecidos', 'lesionados']].copy()
vm = Vv[Vv['modo'].notna()][['id_accidente', 'anio', 'modo']].drop_duplicates()
# atropello -> Peatón como modo-víctima
atro = Sv[Sv['tipoN'] == 'Atropello'][['id_accidente', 'anio']].copy(); atro['modo'] = 'Peatón'
vm = pd.concat([vm, atro], ignore_index=True)
sm = sev.merge(vm, on=['id_accidente', 'anio'], how='inner')
MODOS_SEV = MODOS + ['Peatón']
ms_idx = {m: i for i, m in enumerate(MODOS_SEV)}
g = A(sm, ['cut_com', 'anio', 'modo'], {'n': ('id_accidente', 'size'), 'f': ('fallecidos', 'sum'), 'le': ('lesionados', 'sum')})
FACT_MODO = [[com_idx[r.cut_com], int(r.anio), ms_idx[r.modo], int(r.n), int(r.f), int(r.le)]
             for r in g.itertuples() if r.cut_com in com_idx and r.modo in ms_idx]
# fuga por comuna×año: [comIdx, anio, n_fuga, n_veh]
gf = A(Vv, ['cut_com', 'anio'], {'nv': ('id_accidente', 'size'), 'nfu': ('fuga', 'sum')})
FACT_FUGA = [[com_idx[r.cut_com], int(r.anio), int(r.nfu), int(r.nv)] for r in gf.itertuples()]
print(f'  vehículos: {len(Vv):,} · factVeh={len(FACT_VEH)} factModo={len(FACT_MODO)} factFuga={len(FACT_FUGA)}')

# ---------- personas: pirámide + usuario (conductor involucrado) ----------
print('Cargando personas O.S.2...')
P = pd.read_parquet(os.path.join(OS2, 'os2_personas.parquet'), columns=['anio', 'cut_com', 'calidad', 'sexo', 'edad', 'resultado'])
P = P[P['anio'].between(ANIO_MIN, ANIO_MAX)].copy()
P['cut_com'] = P['cut_com'].astype('string')
P['sx'] = P['sexo'].map(lambda s: 'M' if nc(s).startswith('MASC') else ('F' if nc(s).startswith('FEM') else None))
P['br'] = P['edad'].map(edad_br)
def calidad_n(c):
    u = nc(c)
    if u == 'CONDUCTOR': return 'Conductor'
    if u == 'PASAJERO': return 'Pasajero'
    if u == 'PEATON': return 'Peatón'
    if 'FUGA' in u: return 'Se da a la fuga'
    return None
P['cal'] = P['calidad'].map(calidad_n)
P['resN'] = P['resultado'].map(norm_result)
P['fatal'] = (P['resN'] == 'Fallecido').astype(int)
Pv = P[P['cut_com'].isin(com_idx.keys())].copy()
SEXOS = ['M', 'F']; sx_idx = {s: i for i, s in enumerate(SEXOS)}
br_idx = {b: i for i, b in enumerate(EDAD_BR)}
CALS = ['Conductor', 'Pasajero', 'Peatón', 'Se da a la fuga']; cal_idx = {c: i for i, c in enumerate(CALS)}
# persPir: [comIdx, anio, brIdx, sxIdx, n]  (todas las personas involucradas)
g = A(Pv[Pv['br'].notna() & Pv['sx'].notna()], ['cut_com', 'anio', 'br', 'sx'], {'n': ('edad', 'size')})
PERS_PIR = [[com_idx[r.cut_com], int(r.anio), br_idx[r.br], sx_idx[r.sx], int(r.n)] for r in g.itertuples()]
# persCal: [comIdx, anio, calIdx, sxIdx, n, nFatal]  (usuario × sexo, con letalidad)
g = A(Pv[Pv['cal'].notna() & Pv['sx'].notna()], ['cut_com', 'anio', 'cal', 'sx'],
      {'n': ('edad', 'size'), 'nf': ('fatal', 'sum')})
PERS_CAL = [[com_idx[r.cut_com], int(r.anio), cal_idx[r.cal], sx_idx[r.sx], int(r.n), int(r.nf)] for r in g.itertuples()]
# persCondBr: conductores por edad×sexo: [comIdx, anio, brIdx, sxIdx, n]
cond = Pv[(Pv['cal'] == 'Conductor') & Pv['br'].notna() & Pv['sx'].notna()]
g = A(cond, ['cut_com', 'anio', 'br', 'sx'], {'n': ('edad', 'size')})
PERS_COND = [[com_idx[r.cut_com], int(r.anio), br_idx[r.br], sx_idx[r.sx], int(r.n)] for r in g.itertuples()]
print(f'  personas: {len(Pv):,} · piramide={len(PERS_PIR)} usuario={len(PERS_CAL)} conductores={len(PERS_COND)}')

# ---------- densidad geocodificada: hex H3 res-8 por región y POR MODO (lazy) ----------
# Cada celda = [boundary, cut_com, n_total, f_total, [conteos por modo]] (orden de MODOS_SEV).
# Un siniestro cuenta en cada modo que involucra (peatón vía atropello) -> permite ver la
# distribución espacial de cada modo por separado en el dashboard.
DENS_REG = {}
if h3 is not None:
    NMS = len(MODOS_SEV)
    Sg = Sv[Sv['lat'].notna()][['id_accidente', 'anio', 'cut_com', 'lat', 'lon', 'fallecidos']].copy()
    Sg['reg'] = Sg['cut_com'].str[:2]
    Sg['h3'] = [h3.latlng_to_cell(la, lo, 8) for la, lo in zip(Sg['lat'], Sg['lon'])]
    # conteo por hex × modo (vm = modo-por-siniestro con Peatón, del bloque de vehículos)
    vmi = vm.copy(); vmi['moi'] = vmi['modo'].map(ms_idx)
    Sgm = Sg[['id_accidente', 'anio', 'reg', 'h3']].merge(
        vmi[['id_accidente', 'anio', 'moi']].dropna(), on=['id_accidente', 'anio'], how='inner')
    modecnt = Sgm.groupby(['reg', 'h3', 'moi']).size().reset_index(name='c')
    modemap = {}
    for r in modecnt.itertuples():
        modemap.setdefault((r.reg, r.h3), [0] * NMS)[int(r.moi)] = int(r.c)
    for reg_cod, sub in Sg.groupby('reg'):
        hg = sub.groupby('h3').agg(n=('id_accidente', 'size'), f=('fallecidos', 'sum'),
                                   cut=('cut_com', lambda s: s.mode().iloc[0])).reset_index()
        hg = hg[hg['n'] >= 2]
        arr = []
        for r in hg.itertuples():
            b = h3.cell_to_boundary(r.h3)
            counts = modemap.get((reg_cod, r.h3), [0] * NMS)
            arr.append([[[round(p[1], 5), round(p[0], 5)] for p in b], r.cut, int(r.n), int(r.f), counts])
        json.dump(arr, open(os.path.join(PUB, f'{reg_cod}.json'), 'w', encoding='utf-8'), separators=(',', ':'))
        DENS_REG[reg_cod] = len(arr)
    print(f'  densidad hex: {sum(DENS_REG.values()):,} celdas × {NMS} modos en {len(DENS_REG)} regiones -> data/os2hex/<reg>.json')

# ---------- bundle ----------
OS2DATA = {
    'meta': {
        'generado': BUILD, 'anios': list(range(ANIO_MIN, ANIO_MAX + 1)),
        'fuente': 'Carabineros — Prefectura O.S.2 (Transparencia Proactiva)',
        'nota': ('Siniestros de tránsito reportados por Carabineros O.S.2, 2010–2025. Universo DISTINTO '
                 'de CONASET (no comparables directamente). Categorías normalizadas (los años previos a 2020 '
                 'venían desglosadas). O.S.2 NO identifica al causante: las cifras de conductor son '
                 '"conductores involucrados", no responsables. El 78% con geolocalización se agrega a '
                 'hexágono. Datos referenciales.'),
        'regiones': REGIONES, 'ciudades': CIUDADES,
        'tipos': TIPOS, 'sectores': SECTORES, 'causas': CAUSAS, 'modos': MODOS, 'modosSev': MODOS_SEV,
        'sexos': SEXOS, 'edadBr': EDAD_BR, 'calidades': CALS, 'densReg': DENS_REG,
    },
    'comunas': COMUNAS,
    'factSin': FACT_SIN, 'factCausa': FACT_CAUSA, 'factVeh': FACT_VEH, 'factModo': FACT_MODO, 'factFuga': FACT_FUGA,
    'persPir': PERS_PIR, 'persCal': PERS_CAL, 'persCond': PERS_COND,
}
out = os.path.join(BASE, 'os2_bundle.js')
with open(out, 'w', encoding='utf-8') as f:
    f.write('/* Generado por procesar_os2.py — no editar a mano. */\n')
    f.write('window.OS2 = ')
    json.dump(OS2DATA, f, ensure_ascii=False, separators=(',', ':'))
    f.write(';\n')
mb = os.path.getsize(out) / 1e6
print(f'\nos2_bundle.js -> {mb:.2f} MB · comunas={len(COMUNAS)} ciudades={len(CIUDADES)}')
