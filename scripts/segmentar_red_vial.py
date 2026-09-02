# -*- coding: utf-8 -*-
"""
Segmentación vial (linear referencing): pega cada siniestro al tramo de la Red Vial
Nacional más cercano y agrega conteo + fallecidos por tramo. Precómputo offline para
el modo 'Red vial' del análisis espacial.
Salida: data/parquet/red_vial_siniestros.parquet (tramos con ≥1 siniestro).
"""
import os, warnings
import geopandas as gpd, pandas as pd
warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(BASE, 'data', 'parquet')
MAXDIST = 60  # m: descarta siniestros a más de 60 m de cualquier vía

def main():
    acc = gpd.read_parquet(os.path.join(P, 'siniestros_2020_2025.parquet'), columns=['cod_region', 'fallecidos', 'geometry'])
    acc = acc[acc.geometry.notna() & acc['cod_region'].notna()].to_crs(32719)
    print('siniestros con punto:', len(acc))
    roads = gpd.read_parquet(os.path.join(P, 'cartografia', 'red_vial.parquet'), columns=['nombre', 'nombre_com', 'geometry'])
    roads = roads[roads.geometry.notna()].reset_index(drop=True)
    roads['seg'] = roads.index
    roads_m = roads.to_crs(32719)
    print('tramos de red vial:', len(roads))
    j = gpd.sjoin_nearest(acc, roads_m[['seg', 'geometry']], max_distance=MAXDIST, how='inner')
    print('siniestros pegados a un tramo (<= %dm): %d (%.1f%%)' % (MAXDIST, len(j), 100 * len(j) / len(acc)))
    agg = j.groupby('seg').agg(n=('seg', 'size'), f=('fallecidos', 'sum'),
                               cod_region=('cod_region', lambda s: int(s.mode().iloc[0]))).reset_index()
    out = roads.loc[agg['seg'].values, ['nombre', 'nombre_com', 'geometry']].reset_index(drop=True)
    out['n'] = agg['n'].values; out['f'] = agg['f'].values; out['cod_region'] = agg['cod_region'].values.astype('int16')
    out['geometry'] = out.geometry.simplify(0.0003, preserve_topology=False)  # ~30 m
    out = out[out.geometry.notna() & ~out.geometry.is_empty]
    out.to_parquet(os.path.join(P, 'red_vial_siniestros.parquet'), compression='zstd', index=False)
    mb = os.path.getsize(os.path.join(P, 'red_vial_siniestros.parquet')) / 1e6
    print(f'-> red_vial_siniestros.parquet ({mb:.1f} MB) · tramos con siniestros: {len(out)}')
    print('  dist n por tramo:', out['n'].describe()[['mean', '50%', 'max']].to_dict())

if __name__ == '__main__':
    main()
