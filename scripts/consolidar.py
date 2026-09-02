# -*- coding: utf-8 -*-
"""
Consolida los siniestros individuales 2014-2024 en una única base DEDUPLICADA.
Estrategia: unir todas las capas de siniestros individuales y deduplicar por id_accidente,
prefiriendo el registro 'regional' (incluye zona rural) sobre el 'nacional' (solo urbano).
Esto combina urbano + rural sin doble conteo (validado: los ids se solapan entre ambos niveles).
Salida: data/parquet/siniestros_consolidado.parquet
"""
import os, duckdb

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(BASE, 'data', 'parquet').replace('\\', '/')
OUT = f'{P}/siniestros_consolidado.parquet'

def main():
    con = duckdb.connect()
    con.load_extension('spatial') if _has_spatial(con) else None
    con.execute(f"""
        COPY (
          SELECT * EXCLUDE(rn) FROM (
            SELECT *,
              row_number() OVER (
                PARTITION BY id_accidente
                ORDER BY (nivel='regional') DESC, (cut_com IS NOT NULL) DESC,
                         (zona IS NOT NULL) DESC, (tipo_final IS NOT NULL) DESC
              ) AS rn
            FROM read_parquet('{P}/siniestros_individuales.parquet')
            WHERE id_accidente IS NOT NULL
          ) WHERE rn = 1
          UNION ALL
          SELECT * FROM read_parquet('{P}/siniestros_individuales.parquet')
          WHERE id_accidente IS NULL
        ) TO '{OUT}' (FORMAT parquet, COMPRESSION zstd)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{OUT}')").fetchone()[0]
    print(f'Consolidado deduplicado: {n:,} siniestros -> {OUT}'.replace(',', '.'))
    # cobertura por año: regiones cubiertas y urbano/rural
    print('\nCobertura por año (siniestros deduplicados):')
    df = con.execute(f"""
        SELECT anio,
               count(*) AS siniestros,
               count(DISTINCT cod_region) AS regiones,
               sum(CASE WHEN zona='RURAL' THEN 1 ELSE 0 END) AS rural,
               sum(CASE WHEN zona='URBANA' THEN 1 ELSE 0 END) AS urbana,
               sum(fallecidos) AS fallecidos
        FROM read_parquet('{OUT}')
        GROUP BY anio ORDER BY anio
    """).df()
    print(df.to_string(index=False))
    con.close()

def _has_spatial(con):
    try:
        con.install_extension('spatial'); con.load_extension('spatial'); return True
    except Exception:
        return False

if __name__ == '__main__':
    main()
