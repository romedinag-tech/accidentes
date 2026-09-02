# -*- coding: utf-8 -*-
"""
Crea data/accidentes.duckdb con VISTAS sobre los GeoParquet, para consulta inmediata.
Uso:  import duckdb; con = duckdb.connect('data/accidentes.duckdb'); con.sql('SELECT ...')
Las vistas apuntan a los parquet (rutas absolutas), así que basta reconvertir para actualizar.
"""
import os, duckdb

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(BASE, 'data', 'parquet').replace('\\', '/')
DB = os.path.join(BASE, 'data', 'accidentes.duckdb')

TEMAS = ['puntos_criticos', 'atropellos', 'siniestros_individuales', 'siniestros_en_ruta',
         'motocicletas', 'bicicletas', 'siniestros_urbanos', 'region_multianual']
CARTO = ['comunas', 'regiones', 'provincias', 'red_vial']

def main():
    if os.path.exists(DB):
        os.remove(DB)
    con = duckdb.connect(DB)
    try:
        con.install_extension('spatial'); con.load_extension('spatial')
        spatial = True
    except Exception as e:
        spatial = False
        print('(aviso: extensión spatial no disponible:', e, ')')
    for t in TEMAS:
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{P}/{t}.parquet')")
    for c in CARTO:
        con.execute(f"CREATE VIEW carto_{c} AS SELECT * FROM read_parquet('{P}/cartografia/{c}.parquet')")
    # Vista recomendada: serie "regional" (incluye zona rural, evita el doble conteo con archivos nacionales urbanos)
    con.execute("""
        CREATE VIEW siniestros AS
        SELECT * FROM siniestros_individuales WHERE nivel = 'regional'
    """)
    print('Base creada:', DB, '| spatial:', spatial)
    print('Vistas:', [r[0] for r in con.execute("SELECT table_name FROM information_schema.tables ORDER BY 1").fetchall()])
    # smoke test
    n = con.execute("SELECT count(*) FROM siniestros").fetchone()[0]
    print('siniestros (nivel regional):', n)
    con.close()

if __name__ == '__main__':
    main()
