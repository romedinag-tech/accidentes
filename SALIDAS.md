# SALIDAS — dashboard accidentes

> Contrato de salidas autogenerado desde `_diagnostico_kit/catalogo.json`.
> No editar a mano: corre `python _diagnostico_kit/lib_diagnostico.py --regenerar`.

**Tema:** Siniestralidad vial / accidentes de transito (CONASET)  
**Cobertura:** Chile, 16 regiones · Base 2014-2024; dashboard 2020-2024  
**Llave territorial:** cut_com (comuna INE, join 100% con cartografia/comunas); secundaria cod_region  
**Granularidades:** comuna, region, provincia, punto (siniestro), grilla ~330 m  
**Estado:** operativo · **Privacidad:** Publico: datos abiertos CONASET + cartografia Censo. Sin PII.

## Salidas reutilizables

- **`data/parquet/siniestros_consolidado.parquet`** (parquet · 375489 filas)
  - granularidad: punto (deduplicado por id_accidente, urbano+rural) · llave: `id_accidente; cut_com, cod_region`
  - indicadores: fallecidos, graves, menos_graves, leves, lesionados, tipo_final, causa_final, zona
  - TABLA CLAVE reutilizable: siniestros deduplicados sin doble conteo (urbano+rural).
- **`data/parquet/cartografia/comunas.parquet`** (parquet · 345 filas)
  - granularidad: comuna (poligono) · llave: `cut_com`
  - indicadores: poblacion, viviendas, superficie_km2, densidad
  - Cartografia comunal con poblacion Censo 2017. Llave de join canonica cut_com y base de tasas por 100k.
- **`data/parquet/cartografia/regiones.parquet`** (parquet · 16 filas)
  - granularidad: region · llave: `cod_region`
  - indicadores: poblacion, densidad
  - Cartografia regional con poblacion.
- **`data/accidentes.duckdb`** (duckdb)
  - granularidad: vistas sobre parquet · llave: `cut_com, cod_region, id_accidente`
  - indicadores: vistas: siniestros, atropellos, carto_comunas, ...
  - DuckDB con vistas listas (extension spatial). Vista siniestros = individuales nivel regional (con rural). Interfaz de consulta recomendada.

## Consulta de ejemplo

```
import duckdb; con=duckdb.connect('data/accidentes.duckdb'); con.load_extension('spatial'); con.sql("SELECT cut_com, count(*) n, sum(fallecidos) fallecidos FROM 'data/parquet/siniestros_consolidado.parquet' GROUP BY cut_com").df()
```

## Trampas (no tropezar)

- DOBLE CONTEO en siniestros_individuales: cada anio 2020-2024 aparece 2 veces (nivel nacional=solo urbano, regional=con rural). Usar siniestros_consolidado (ya deduplicado).
- atropellos/motos/bicis/urbanos/en_ruta son SUBCONJUNTOS: no sumar con la tabla principal.
- Usar columnas canonicas (region_norm, tipo_final, causa_final), no las crudas o_*.
- cut_com viene en float/int/str segun capa: castear al unir.

## Como regenerar

`python scripts/convertir_parquet.py; python scripts/consolidar.py; python scripts/crear_duckdb.py; python procesar_accidentes.py`

## Docs clave

`README.md`, `data/parquet/DICCIONARIO.md`, `data/CATALOGO_CONASET.md`
