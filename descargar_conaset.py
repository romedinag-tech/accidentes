# -*- coding: utf-8 -*-
"""
Descarga exhaustiva de capas de siniestros de tránsito de CONASET
Portal ArcGIS Open Data: https://mapas-conaset.opendata.arcgis.com
Descarga los shapefiles (ZIP) de todos los datasets del catálogo DCAT.
"""
import os, re, csv, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "CONASET")
MANIFEST = os.path.join(BASE, "data", "conaset_manifest.csv")

def theme(t):
    tl = t.lower()
    if 'punto' in tl and 'critico' in tl: return '01_Puntos_criticos'
    if 'atropello' in tl: return '02_Atropellos'
    if 'siniestros individuales' in tl: return '03_Siniestros_individuales'
    if 'en ruta' in tl: return '04_Siniestros_en_ruta'
    if 'motocicleta' in tl: return '05_Motocicletas'
    if 'bicicleta' in tl: return '06_Bicicletas'
    if 'urbanos' in tl: return '07_Siniestros_urbanos'
    if 'siniestros de tr' in tl: return '08_Region_multianual'
    return '09_Otros'

def sanitize(t):
    t = (t.replace('ó','o').replace('í','i').replace('á','a').replace('é','e')
          .replace('ú','u').replace('ñ','n').replace('Ñ','N').replace('�','')
          .replace('Á','A').replace('É','E').replace('Í','I').replace('Ó','O').replace('Ú','U'))
    t = re.sub(r'[^A-Za-z0-9 _-]', '', t).strip()
    return re.sub(r'\s+', '_', t)

def load_catalog():
    dcat = os.path.join(BASE, "data", "conaset_dcat.json")
    d = json.load(open(dcat, encoding='utf-8'))
    items = []
    for x in d['dataset']:
        dists = {dd.get('format'): dd.get('accessURL') for dd in x.get('distribution', [])}
        shp = dists.get('ZIP')
        if not shp:
            continue
        items.append(dict(title=x['title'], theme=theme(x['title']),
                          shp=shp, geojson=dists.get('GeoJSON', ''),
                          csv=dists.get('CSV', ''), landing=x.get('landingPage', '')))
    return items

def download(item):
    folder = os.path.join(OUT, item['theme'])
    os.makedirs(folder, exist_ok=True)
    fname = sanitize(item['title']) + '.zip'
    path = os.path.join(folder, fname)
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return (item['title'], 'skip', os.path.getsize(path))
    for attempt in range(3):
        try:
            r = requests.get(item['shp'], timeout=180)
            if r.status_code == 200 and r.headers.get('content-type','').startswith('application/zip'):
                with open(path, 'wb') as f:
                    f.write(r.content)
                return (item['title'], 'ok', len(r.content))
            time.sleep(3)
        except Exception as e:
            last = str(e); time.sleep(4)
    return (item['title'], 'FAIL', 0)

def main():
    os.makedirs(OUT, exist_ok=True)
    items = load_catalog()
    print(f"Total datasets con shapefile: {len(items)}")
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(download, it): it for it in items}
        for i, fut in enumerate(as_completed(futs), 1):
            title, status, size = fut.result()
            results.append((title, status, size))
            print(f"[{i:3d}/{len(items)}] {status:4s} {size/1e6:7.2f}MB  {title[:55]}")
    ok = sum(1 for _,s,_ in results if s in ('ok','skip'))
    fail = [t for t,s,_ in results if s == 'FAIL']
    total = sum(sz for _,_,sz in results)
    print(f"\nOK/skip: {ok}  FAIL: {len(fail)}  Total: {total/1e6:.1f} MB")
    if fail:
        print("Fallidos:")
        for t in fail: print("  -", t)
    # write log
    with open(os.path.join(OUT, "_descarga_log.csv"), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['title','status','bytes'])
        w.writerows(results)

if __name__ == '__main__':
    main()
