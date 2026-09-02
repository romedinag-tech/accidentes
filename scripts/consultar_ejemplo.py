# -*- coding: utf-8 -*-
"""
Ejemplos de consulta sobre la base eficiente (DuckDB + GeoParquet).
Ejecutar:  python scripts/consultar_ejemplo.py
"""
import os, duckdb
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
con = duckdb.connect(os.path.join(BASE, 'data', 'accidentes.duckdb'))
con.load_extension('spatial')

print('\n1) Fallecidos y siniestros por año (serie regional, incluye rural):')
print(con.sql("""
    SELECT anio, count(*) AS siniestros, sum(fallecidos) AS fallecidos, sum(graves) AS graves
    FROM siniestros GROUP BY anio ORDER BY anio
""").df().to_string(index=False))

print('\n2) Top 10 comunas por fallecidos (con tasa por 100k hab.):')
print(con.sql("""
    SELECT c.comuna, c.region_norm, sum(s.fallecidos) AS fallecidos,
           round(100000.0*sum(s.fallecidos)/max(c.poblacion),1) AS tasa_100k
    FROM siniestros s JOIN carto_comunas c USING (cut_com)
    GROUP BY c.comuna, c.region_norm ORDER BY fallecidos DESC LIMIT 10
""").df().to_string(index=False))

print('\n3) Distribución por tipo de siniestro:')
print(con.sql("""
    SELECT tipo_final AS tipo, count(*) AS n
    FROM siniestros WHERE tipo_final IS NOT NULL
    GROUP BY tipo_final ORDER BY n DESC LIMIT 10
""").df().to_string(index=False))
con.close()
