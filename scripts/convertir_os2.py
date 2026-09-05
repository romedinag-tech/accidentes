# -*- coding: utf-8 -*-
"""Consolida los 48 Excel crudos de Carabineros O.S.2 (data/OS2/{siniestros,personas,vehiculos}/,
2010-2025, esquemas variables por año) en 3 parquets canónicos + un DuckDB consultable.

Salida (data/OS2/):
  parquet/os2_siniestros.parquet   parquet/os2_personas.parquet   parquet/os2_vehiculos.parquet
  os2.duckdb  (tablas: siniestros, personas, vehiculos)

Decisiones:
- Esquema canónico por reporte (nombres estables), con mapeo de alias por año.
- La COMUNA se resuelve por CONTENIDO (no por nombre de columna): la columna numérica es el
  código, la de texto es el nombre. Se deriva `cut_com` (5 díg.) uniendo por nombre normalizado
  contra la cartografía comunal, para que sea joinable con CONASET.
- `fecha` se parsea desde datetime o desde serial Excel (pyxlsb entrega números).
- No se toca ningún crudo; los parquet son archivos nuevos.
"""
import os, glob, re, unicodedata, warnings, collections
import pandas as pd
warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data', 'OS2')
OUTDIR = os.path.join(RAW, 'parquet')
CART = os.path.join(BASE, 'data', 'parquet', 'cartografia', 'comunas.parquet')

def nrm(t):
    t = unicodedata.normalize('NFKD', str(t)).encode('ascii', 'ignore').decode().lower().strip()
    return re.sub(r'\s+', ' ', t)

def nc(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9 ]', ' ', s).strip()

# alias de columna (normalizada) -> canónica. tipo/causa/comuna se tratan aparte.
ALIAS = {
    'idaccidente': 'id_accidente', 'id': 'id_accidente',
    'fecha': 'fecha', 'mes': 'mes', 'hora': 'hora',
    'region': 'region', 'zona': 'region',
    'calidad': 'calidad', 'sexo': 'sexo', 'edad': 'edad', 'resultado': 'resultado',
    'servicio': 'servicio',
    'muertos': 'fallecidos', 'fallecidos': 'fallecidos', 'fallecido': 'fallecidos',
    'graves': 'graves', 'grave': 'graves',
    'm/grave': 'menos_graves', 'm_grave': 'menos_graves',
    'leves': 'leves', 'leve': 'leves', 'ilesos': 'ilesos', 'ileso': 'ilesos',
    'calleuno': 'calle_1', 'calle 1': 'calle_1', 'calle_1': 'calle_1',
    'calledos': 'calle_2', 'calle 2': 'calle_2', 'calle_2': 'calle_2',
    'frentenumero': 'numero', 'ruta': 'ruta', 'rolruta': 'ruta',
    'ubicacion km': 'km', 'ubicacionkm': 'km', 'km': 'km',
    'parte nro.': 'parte', 'parte': 'parte', 'tribunal': 'tribunal',
    'sector': 'sector', 'urbano/rural': 'sector',
}
SEV = ['fallecidos', 'graves', 'menos_graves', 'leves', 'ilesos']

# cartografía: nombre normalizado -> cut_com
_cart = pd.read_parquet(CART, columns=['cut_com', 'comuna'])
NAME2CUT = {nc(n): str(c).zfill(5) for n, c in zip(_cart['comuna'], _cart['cut_com'])}

def parse_fecha(s):
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_datetime(s, unit='D', origin='1899-12-30', errors='coerce')
    return pd.to_datetime(s, errors='coerce', dayfirst=True)

def canonize(df, report):
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    out = pd.DataFrame(index=df.index)
    # --- comuna: por contenido ---
    cod_col = name_col = None
    for c in df.columns:
        k = nrm(c)
        if k == 'codcomuna': cod_col = c
        elif k == 'nomcomuna': name_col = c
    for c in df.columns:
        k = nrm(c)
        if k in ('comuna', 'comunas', 'comuna2'):
            s = df[c].dropna().head(80)
            num = pd.to_numeric(s, errors='coerce').notna().mean() > 0.8 if len(s) else False
            if num and cod_col is None: cod_col = c
            elif (not num) and name_col is None: name_col = c
    out['cod_comuna'] = (pd.to_numeric(df[cod_col], errors='coerce').astype('Int64').astype('string')
                         .str.zfill(5)) if cod_col else pd.NA
    out['comuna'] = df[name_col].astype('string').str.strip() if name_col else pd.NA
    # cut_com: del código si es válido, si no por nombre normalizado
    def to_cut(row):
        c = row['cod_comuna']
        if pd.notna(c) and str(c) in set(NAME2CUT.values()): return str(c)
        n = row['comuna']
        return NAME2CUT.get(nc(n)) if pd.notna(n) else None
    out['cut_com'] = out.apply(to_cut, axis=1)
    # --- tipo / causa: elegir la columna de TEXTO (no la de código); 2024 duplica ambas ---
    cols_n = {nrm(c): c for c in df.columns}
    def pick_text(names):
        cands = [cols_n[n] for n in names if n in cols_n]
        for c in cands:
            s = df[c].dropna().head(80)
            if len(s) and pd.to_numeric(s, errors='coerce').notna().mean() < 0.5:
                return c
        return cands[0] if cands else None
    if report == 'vehiculos':
        tcol = cols_n.get('tipo')
        if tcol: out['tipo'] = df[tcol].astype('string').str.strip()
    else:
        tcol = pick_text(['siniestros', 'tipoaccdte', 'accdtes.', 'tipo'])
        out['tipo'] = df[tcol].astype('string').str.strip() if tcol else pd.NA
    if report == 'siniestros':
        ccol = pick_text(['causas', 'causa'])
        out['causa'] = df[ccol].astype('string').str.strip() if ccol else pd.NA
    # --- alias directos ---
    for c in df.columns:
        k = nrm(c); canon = ALIAS.get(k)
        if canon and canon not in out.columns and canon not in ('tipo', 'causa'):
            out[canon] = df[c]
    # --- tipos ---
    def to_int(s):
        return pd.to_numeric(s, errors='coerce').astype('Float64').round().astype('Int64')
    if 'fecha' in out:
        out['fecha'] = parse_fecha(out['fecha'])
        # mes/dia_semana derivados de la fecha (el 'Mes' crudo viene como texto en años viejos)
        out['mes'] = out['fecha'].dt.month.astype('Int64')
        out['dia_semana'] = (out['fecha'].dt.dayofweek + 1).astype('Int64')  # 1=Lun..7=Dom
    for col in ['hora', 'edad', 'id_accidente'] + SEV:
        if col in out: out[col] = to_int(out[col])
    for col in ['region', 'sector', 'calidad', 'sexo', 'resultado', 'servicio',
                'calle_1', 'calle_2', 'numero', 'ruta', 'km', 'parte', 'tribunal']:
        if col in out: out[col] = out[col].astype('string').str.strip()
    return out

CANON = {
    'siniestros': ['id_accidente', 'anio', 'fecha', 'mes', 'dia_semana', 'hora', 'cut_com', 'cod_comuna',
                   'comuna', 'region', 'tipo', 'causa', 'sector', 'fallecidos', 'graves', 'menos_graves',
                   'leves', 'ilesos', 'calle_1', 'calle_2', 'numero', 'ruta', 'km', 'parte', 'tribunal'],
    'personas': ['id_accidente', 'anio', 'fecha', 'mes', 'dia_semana', 'hora', 'cut_com', 'cod_comuna',
                 'comuna', 'region', 'calidad', 'sexo', 'edad', 'resultado'],
    'vehiculos': ['id_accidente', 'anio', 'fecha', 'mes', 'dia_semana', 'hora', 'cut_com', 'cod_comuna',
                  'comuna', 'region', 'tipo', 'servicio'],
}

def convertir(report):
    partes = []
    for y in range(2010, 2026):
        fs = glob.glob(os.path.join(RAW, report, f'os2_*_{y}.*'))
        if not fs: continue
        f = fs[0]; eng = 'pyxlsb' if f.endswith('.xlsb') else 'openpyxl'
        raw = pd.read_excel(f, engine=eng)
        c = canonize(raw, report)
        c['anio'] = y
        partes.append(c)
        print(f'  {report} {y}: {len(c):>6} filas  (cut_com no-nulo {100*c["cut_com"].notna().mean():.0f}%)')
    df = pd.concat(partes, ignore_index=True)
    for col in CANON[report]:
        if col not in df.columns: df[col] = pd.NA
    df = df[CANON[report]]
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f'os2_{report}.parquet')
    df.to_parquet(out, compression='zstd', index=False)
    print(f'-> {out}  ({len(df):,} filas, {os.path.getsize(out)/1e6:.1f} MB)')
    return df

if __name__ == '__main__':
    import sys
    reps = sys.argv[1:] or ['siniestros', 'personas', 'vehiculos']
    for r in reps:
        print(f'\n### {r.upper()} ###')
        convertir(r)
    # DuckDB consultable
    try:
        import duckdb
        db = os.path.join(RAW, 'os2.duckdb')
        if os.path.exists(db): os.remove(db)
        con = duckdb.connect(db)
        for r in ['siniestros', 'personas', 'vehiculos']:
            p = os.path.join(OUTDIR, f'os2_{r}.parquet')
            if os.path.exists(p):
                con.execute(f"CREATE TABLE {r} AS SELECT * FROM read_parquet('{p}')")
        con.close()
        print(f'\n-> {db} (tablas: siniestros, personas, vehiculos)')
    except Exception as e:
        print('DuckDB no generado:', e)
