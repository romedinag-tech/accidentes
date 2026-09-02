# -*- coding: utf-8 -*-
"""
Descarga la base consolidada Base_SINIESTROS_2020_2025 de CONASET (FeatureServer
paginado) a un parquet crudo. 436k siniestros 2020-2025, urbano+rural, con banderas
de modo involucrado (Atropello/Bicicleta/Motociclet) y dos clasificaciones de causa.
"""
import os, time, requests, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'data', 'CONASET_2020_2025', 'base_2020_2025_cruda.parquet')
URL = ('https://services3.arcgis.com/vaJl1B5HEzZj7154/arcgis/rest/services/'
       'Base_SINIESTROS_2020_2025/FeatureServer/0/query')
STEP = 2000

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    total = requests.get(URL, params={'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'},
                         timeout=60).json()['count']
    print('total features:', total)
    rows, off = [], 0
    while off < total:
        for intento in range(4):
            try:
                r = requests.get(URL, params={'where': '1=1', 'outFields': '*', 'returnGeometry': 'false',
                    'orderByFields': 'FID', 'resultOffset': off, 'resultRecordCount': STEP, 'f': 'json'},
                    timeout=120).json()
                feats = r.get('features', [])
                rows.extend(f['attributes'] for f in feats)
                break
            except Exception as e:
                print('  reintento', off, e); time.sleep(4)
        else:
            print('FALLO en offset', off); break
        off += STEP
        if off % 20000 == 0:
            print(f'  {off}/{total}...')
    df = pd.DataFrame(rows)
    print('descargado:', len(df), 'filas ·', len(df.columns), 'columnas')
    print('columnas:', list(df.columns))
    df.to_parquet(OUT, compression='zstd', index=False)
    print('->', OUT, f'({os.path.getsize(OUT)/1e6:.1f} MB)')

if __name__ == '__main__':
    main()
