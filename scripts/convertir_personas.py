# -*- coding: utf-8 -*-
"""
Convierte la base cruda de personas (personas_cruda.parquet) a la base canónica de la
FASE 2: accidentados por edad / rol / tipo de usuario / sexo, a nivel persona.
Salida: data/parquet/personas.parquet
"""
import os, sys, warnings
import pandas as pd, numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convertir_parquet import norm_region, norm_zona, repair, COD2NOMBRE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'data', 'CONASET_2020_2025', 'personas_cruda.parquet')
OUT = os.path.join(BASE, 'data', 'parquet', 'personas.parquet')

def main():
    df = pd.read_parquet(SRC)
    print('filas crudas:', len(df))
    out = pd.DataFrame(index=df.index)
    out['anio'] = pd.to_numeric(df['Año'], errors='coerce').astype('Int64')
    reg = df['Region'].map(repair)
    mp = {v: norm_region(v) for v in reg.dropna().unique()}
    out['cod_region'] = reg.map(lambda v: mp.get(v, (None, None))[0]).astype('Int64')
    out['region_norm'] = reg.map(lambda v: mp.get(v, (None, None))[1])
    out['comuna'] = df['Comuna'].map(repair)
    out['zona'] = df['Zona'].map(norm_zona)
    out['cat_edad'] = df['Categoria_edad'].map(repair)
    out['rango_etareo'] = df['Rango_etareo'].map(repair)
    out['usuario'] = df['Categoria_CONASET'].map(repair)      # Automóvil, Peatón, Bus/Taxibus, Camión...
    out['rol'] = df['Calidad'].map(repair)                    # CONDUCTOR/PASAJERO/PEATON
    out['sexo'] = df['Sexo'].map(repair)
    out['servicio'] = df['Servicio'].map(repair)
    edad = pd.to_numeric(df['Edad'], errors='coerce')
    out['edad'] = edad.where((edad >= 0) & (edad <= 120)).astype('Int64')  # 999 = no informa -> NaN
    for c, o in [('fallecidos', 'Fallecidos'), ('graves', 'Graves'), ('menos_graves', 'Menos_Graves'),
                 ('leves', 'Leves'), ('lesionados', 'Lesionados_total')]:
        out[c] = pd.to_numeric(df[o], errors='coerce').fillna(0).astype('int32')
    out['id_accidente'] = pd.to_numeric(df['Idaccidente'], errors='coerce').astype('Int64')
    out.to_parquet(OUT, compression='zstd', index=False)
    print('->', OUT, f'({os.path.getsize(OUT)/1e6:.1f} MB)')
    print('años:', out['anio'].value_counts().sort_index().to_dict())
    print('cat_edad:', out['cat_edad'].value_counts().to_dict())
    print('usuarios:', out['usuario'].value_counts().head(6).to_dict())
    print('region_norm no-nulo: %.1f%%' % (out['region_norm'].notna().mean() * 100))

if __name__ == '__main__':
    main()
