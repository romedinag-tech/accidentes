# -*- coding: utf-8 -*-
"""
Descarga la base de PERSONAS/participantes (Base_de_persona_vehiculo_4) de CONASET,
que alimenta los dashboards 'Usuarios vulnerables' y 'Características de los participantes'.
Nivel persona (770k), con edad, grupo etario, sexo, rol (calidad), tipo de usuario/vehículo
(incluye bus, camión...) y severidad por persona. Base de la FASE 2 (accidentados por edad).
"""
import os, time, requests, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'data', 'CONASET_2020_2025', 'personas_cruda.parquet')
LAYER = ('https://services3.arcgis.com/vaJl1B5HEzZj7154/arcgis/rest/services/'
         'Base_de_persona_vehiculo_4/FeatureServer/0')
URL = LAYER + '/query'

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # paso = maxRecordCount del servicio (evita saltar registros al paginar)
    STEP = requests.get(LAYER, params={'f': 'json'}, timeout=60).json().get('maxRecordCount', 1000)
    total = requests.get(URL, params={'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'}, timeout=60).json()['count']
    print('total personas:', total, '| paso:', STEP)
    rows, off = [], 0
    while off < total:
        for _ in range(4):
            try:
                r = requests.get(URL, params={'where': '1=1', 'outFields': '*', 'returnGeometry': 'false',
                    'orderByFields': 'ObjectId', 'resultOffset': off, 'resultRecordCount': STEP, 'f': 'json'},
                    timeout=120).json()
                rows.extend(f['attributes'] for f in r.get('features', []))
                break
            except Exception as e:
                print('  reintento', off, e); time.sleep(4)
        else:
            print('FALLO offset', off); break
        off += STEP
        if off % 40000 == 0:
            print(f'  {off}/{total}...')
    df = pd.DataFrame(rows)
    print('descargado:', len(df), 'filas ·', len(df.columns), 'cols')
    df.to_parquet(OUT, compression='zstd', index=False)
    print('->', OUT, f'({os.path.getsize(OUT)/1e6:.1f} MB)')
    print('años:', sorted(pd.to_numeric(df['Año'], errors='coerce').dropna().astype(int).unique().tolist()))

if __name__ == '__main__':
    main()
