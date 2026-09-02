# -*- coding: utf-8 -*-
"""
Convierte la base cruda Base_SINIESTROS_2020_2025 a la base canónica del dashboard.
Añade: modo involucrado (Peatón/Motocicleta/Bicicleta/Vehículo, por prioridad),
causa agrupada (CAUSA_NUEV), zona urbano/rural, área metropolitana, y 2025.
Reutiliza la maquinaria de encoding/región/cut de convertir_parquet.py.
Salida: data/parquet/siniestros_2020_2025.parquet
"""
import os, sys, warnings
import pandas as pd, numpy as np, geopandas as gpd
from shapely import points
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convertir_parquet import (norm_region, norm_zona, comuna_key, get_comuna_lookup,
                               COD2NOMBRE, repair)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'data', 'CONASET_2020_2025', 'base_2020_2025_cruda.parquet')
OUT = os.path.join(BASE, 'data', 'parquet', 'siniestros_2020_2025.parquet')

def main():
    df = pd.read_parquet(SRC)
    n = len(df)
    print('filas crudas:', n)
    out = pd.DataFrame(index=df.index)
    # temporalidad
    out['anio'] = pd.to_numeric(df['AÑO'], errors='coerce').astype('Int64')
    fecha = pd.to_datetime(df['FECHA'], errors='coerce', utc=True)
    out['fecha'] = fecha
    out['mes'] = fecha.dt.month.astype('Int64')
    out['dia_semana'] = (fecha.dt.dayofweek + 1).astype('Int64')   # 1=Lun..7=Dom
    h = pd.to_numeric(df['Hora_aprox'], errors='coerce')
    out['hora'] = h.where((h >= 0) & (h <= 23)).astype('Int64')
    # territorio
    reg = df['REGION'].map(repair)
    mp = {v: norm_region(v) for v in reg.dropna().unique()}
    out['cod_region'] = reg.map(lambda v: mp.get(v, (None, None))[0]).astype('Int64')
    out['region_norm'] = reg.map(lambda v: mp.get(v, (None, None))[1])
    out['comuna'] = df['COMUNA'].map(repair)
    lu = get_comuna_lookup()
    out['cut_com'] = [lu.get((int(cod), comuna_key(nom))) if pd.notna(cod) and isinstance(nom, str) else None
                      for cod, nom in zip(out['cod_region'], out['comuna'])]
    out['area_metro'] = df['AM'].map(repair).replace('', np.nan)
    out['zona'] = df['ZONA'].map(norm_zona)
    # clasificaciones
    out['tipo'] = df['TIPO__CONA'].map(repair)
    out['tipo_detalle'] = df['TIPO_SINIE'].map(repair)
    out['causa'] = df['CAUSA_NUEV'].map(repair)          # agrupada (16 categorías)
    out['causa_detalle'] = df['CAUSA_SINI'].map(repair)  # detallada (Carabineros)
    # modo involucrado (prioridad Peatón > Moto > Bici > Vehículo)
    atr = pd.to_numeric(df['Atropello'], errors='coerce').fillna(0) == 1
    mot = pd.to_numeric(df['Motociclet'], errors='coerce').fillna(0) == 1
    bic = pd.to_numeric(df['Bicicleta'], errors='coerce').fillna(0) == 1
    out['modo'] = np.select([atr, mot, bic], ['Peatón', 'Motocicleta', 'Bicicleta'], default='Vehículo')
    out['f_peaton'] = atr.astype('int8'); out['f_moto'] = mot.astype('int8'); out['f_bici'] = bic.astype('int8')
    # severidad
    for c, o in [('fallecidos', 'FALLECIDOS'), ('graves', 'GRAVES'), ('menos_graves', 'MENOS_GRAV'),
                 ('leves', 'LEVES'), ('lesionados', 'TOTAL_LESI')]:
        out[c] = pd.to_numeric(df[o], errors='coerce').fillna(0).astype('int32')
    # coordenadas
    out['lat'] = pd.to_numeric(df['Latitud'], errors='coerce')
    out['lon'] = pd.to_numeric(df['longitud'], errors='coerce')
    out['id_siniestro'] = pd.to_numeric(df['ID'], errors='coerce').astype('Int64')

    ok = out['lat'].notna() & out['lon'].notna()
    geom = gpd.GeoSeries([None] * n, index=out.index)
    geom.loc[ok] = gpd.GeoSeries(points(out.loc[ok, 'lon'].values, out.loc[ok, 'lat'].values), index=out[ok].index)
    g = gpd.GeoDataFrame(out, geometry=geom, crs=4326)
    g.to_parquet(OUT, compression='zstd', index=False)
    mb = os.path.getsize(OUT) / 1e6
    print(f'-> {OUT} ({mb:.1f} MB)')
    print('cut_com no-nulo: %.1f%%' % (out['cut_com'].notna().mean() * 100))
    print('region_norm no-nulo: %.1f%%' % (out['region_norm'].notna().mean() * 100))
    print('modo:', out['modo'].value_counts().to_dict())
    print('por año:', out['anio'].value_counts().sort_index().to_dict())

if __name__ == '__main__':
    main()
