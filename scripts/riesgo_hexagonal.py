# -*- coding: utf-8 -*-
"""
Mapa de riesgo hexagonal: cruza accidentes con población (Censo 2024) por hexágono H3,
revelando dónde el riesgo es desproporcionado a resolución fina (~460 m), no por comuna.

- Población: Censo 2024 por manzana (n_per) unido por MANZENT a la geometría de manzanas.
- Se asigna cada manzana (centroide) y cada accidente a su celda H3 (resolución 8).
- Tasa = siniestros por cada 1.000 habitantes (acumulado 2020-2025) por hexágono.
Salida: data/riesgo/<cod_region>.json = [[boundary_lonlat, siniestros, poblacion, tasa, fallecidos], ...]

Lee (solo lectura) el censo y las manzanas de los assets de Análisis RMG.
"""
import os, json, glob, warnings, collections
import pandas as pd, geopandas as gpd
import h3
from shapely.geometry import shape
warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RMG = os.path.dirname(BASE)  # Análisis RMG
CENSO = os.path.join(RMG, 'GIS Gran Concepción', 'Analisis uso de suelo Gran Concepción',
                     'Censo', 'parquet', 'censo2024_manzana_entidad.parquet')
MZDIR = os.path.join(RMG, 'elecciones', 'data', 'manzanas')
ACC = os.path.join(BASE, 'data', 'parquet', 'siniestros_2020_2025.parquet')
OUT = os.path.join(BASE, 'data', 'riesgo')
RES = 8            # H3 res 8 ~ 0.74 km² (~860 m de ancho)
MINPOB = 100       # celdas con menos población no dan tasa confiable
MINACC = 2

def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    # 1) población 2024 por manzent
    cen = pd.read_parquet(CENSO, columns=['MANZENT', 'n_per'])
    cen['n_per'] = pd.to_numeric(cen['n_per'], errors='coerce').fillna(0)
    pob_mz = dict(zip(cen['MANZENT'].astype(str), cen['n_per']))
    print('manzanas censo 2024:', len(pob_mz))
    # 2) manzana centroide -> H3 -> población
    pob_h3 = collections.defaultdict(float)
    nmz = 0
    for gj in glob.glob(os.path.join(MZDIR, '*.geojson')):
        try:
            d = json.load(open(gj, encoding='utf-8'))
        except Exception:
            continue
        for ft in d['features']:
            mz = ft['properties'].get('manzent')
            pob = pob_mz.get(str(mz))
            if not pob or pob <= 0:
                continue
            try:
                c = shape(ft['geometry']).centroid
                cell = h3.latlng_to_cell(c.y, c.x, RES)
            except Exception:
                continue
            pob_h3[cell] += pob
            nmz += 1
    print('manzanas geolocalizadas:', nmz, '· celdas con población:', len(pob_h3))
    # 3) accidentes -> H3 (siniestros, fallecidos, región mayoritaria)
    acc = pd.read_parquet(ACC, columns=['lat', 'lon', 'fallecidos', 'cod_region'])
    acc = acc[acc['lat'].notna() & acc['lon'].notna() & acc['cod_region'].notna()]
    acc_h3 = collections.defaultdict(lambda: [0, 0])
    reg_h3 = collections.defaultdict(collections.Counter)
    for la, lo, fa, reg in zip(acc['lat'].values, acc['lon'].values,
                               acc['fallecidos'].values, acc['cod_region'].values):
        if la < -56 or la > -17 or lo < -110 or lo > -66:
            continue
        cell = h3.latlng_to_cell(float(la), float(lo), RES)
        a = acc_h3[cell]; a[0] += 1; a[1] += int(fa or 0)
        reg_h3[cell][int(reg)] += 1
    print('celdas con accidentes:', len(acc_h3))
    # 4) combinar y armar por región
    by_reg = collections.defaultdict(list)
    for cell, (nacc, nfa) in acc_h3.items():
        pob = pob_h3.get(cell, 0)
        if nacc < MINACC or pob < MINPOB:
            continue
        tasa = nacc / pob * 1000.0
        cod = reg_h3[cell].most_common(1)[0][0]
        bnd = h3.cell_to_boundary(cell)   # [(lat,lon), ...]
        coords = [[round(lo, 5), round(la, 5)] for la, lo in bnd]
        by_reg[cod].append([coords, int(nacc), int(round(pob)), round(tasa, 2), int(nfa)])
    tot = 0
    for cod, arr in by_reg.items():
        json.dump(arr, open(os.path.join(OUT, f'{cod}.json'), 'w', encoding='utf-8'), separators=(',', ':'))
        tot += len(arr)
    print(f'-> {len(by_reg)} regiones, {tot} hexágonos de riesgo en data/riesgo/')

if __name__ == '__main__':
    main()
