"""Visual layers for the CG Civ map: land cover per hex (ESA WorldCover 2021),
a ring of context hexes (Adriatic and neighbouring countries) and rivers (OSM).
Output: build/cgviz.json, coordinates in the site's hex units (R = 1)."""
import json, math, os, glob
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.ops import unary_union, linemerge
from PIL import Image
from pyproj import Transformer
import rasterio
from rasterio.enums import Resampling

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
BUILD = os.path.join(HERE, '..', 'build')
R = 1750.0
W, H = math.sqrt(3) * R, 1.5 * R
UTM = 'EPSG:32634'
to_utm = Transformer.from_crs('EPSG:4326', UTM, always_xy=True)
to_ll = Transformer.from_crs(UTM, 'EPSG:4326', always_xy=True)

kb = gpd.read_file(os.path.join(RAW, 'kontur.gpkg'))
mb = kb[kb.admin_level == 6].to_crs(UTM)
country = unary_union(mb.geometry)
lakes = gpd.read_file(os.path.join(RAW, 'ne_lakes.geojson'))
skadar = lakes[lakes['name'] == 'Lake Skadar'].to_crs(UTM).geometry.iloc[0]
minx, miny, maxx, maxy = country.buffer(9000).bounds   # same origin as build_hex.py

def center(q, r): return (minx + W * (q + r / 2), miny + H * r)
def unit(x, y): return (round((x - minx) / R, 3), round(-(y - miny) / R, 3))

D = json.load(open(os.path.join(BUILD, 'cgciv.json')))
known = {(h['q'], h['r']): h for h in D['hexes']}

# ---------- DEM (terrarium z10, same tiles as build_hex.py) ----------
Z = 10
tiles = glob.glob(os.path.join(RAW, 'dem', f'{Z}_*.png'))
xs = sorted({int(os.path.basename(t).split('_')[1]) for t in tiles})
ys = sorted({int(os.path.basename(t).split('_')[2].split('.')[0]) for t in tiles})
mos = np.zeros((len(ys) * 256, len(xs) * 256), dtype=np.float32)
for t in tiles:
    _, x, y = os.path.basename(t)[:-4].split('_')
    a = np.asarray(Image.open(t).convert('RGB')).astype(np.float32)
    mos[ys.index(int(y)) * 256:(ys.index(int(y)) + 1) * 256, xs.index(int(x)) * 256:(xs.index(int(x)) + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
n2 = 2 ** Z
lon0, lon1 = xs[0] / n2 * 360 - 180, (xs[-1] + 1) / n2 * 360 - 180
def lat_of(ty): return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n2))))
lat1, lat0 = lat_of(ys[0]), lat_of(ys[-1] + 1)
def elev(lon, lat):
    px = (lon + 180) / 360 * n2 * 256 - xs[0] * 256
    py = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n2 * 256 - ys[0] * 256
    return float(mos[min(mos.shape[0] - 1, max(0, int(py))), min(mos.shape[1] - 1, max(0, int(px)))])

# ---------- WorldCover mosaic, decimated to ~60 m ----------
DEC = 6
blo, bla0, bla1, bhi = 18.2, 41.6, 44.0, 20.8
res = 1 / 12000 * DEC
WC = np.zeros((int((bla1 - bla0) / res), int((bhi - blo) / res)), dtype=np.uint8)
for f in glob.glob(os.path.join(RAW, 'wc', '*.tif')):
    with rasterio.open(f) as src:
        L, B, Rr, T = src.bounds
        la0, la1 = max(B, bla0), min(T, bla1)
        if la0 >= la1: continue
        win = src.window(blo, la0, bhi, la1)
        rows, cols = int(round((la1 - la0) / res)), WC.shape[1]
        arr = src.read(1, window=win, out_shape=(rows, cols), resampling=Resampling.mode)
        r0 = int(round((bla1 - la1) / res))
        rows = min(rows, WC.shape[0] - r0); arr = arr[:rows]
        WC[r0:r0 + rows, :] = np.where(arr > 0, arr, WC[r0:r0 + rows, :])
print('worldcover', WC.shape, np.bincount(WC.ravel(), minlength=101)[[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]])
CLS = {10: 'forest', 20: 'shrub', 30: 'grass', 40: 'crop', 50: 'built', 60: 'bare', 70: 'snow', 80: 'water', 90: 'wet', 95: 'wet', 100: 'grass'}
# sample points inside a hex (fractions of R)
SP = [(u * .85, v * .85) for u in np.linspace(-1, 1, 11) for v in np.linspace(-1, 1, 11) if u * u + v * v <= 1]
def cover(x, y):
    cnt = {}
    for u, v in SP:
        lon, lat = to_ll.transform(x + u * R, y + v * R)
        i, j = int((bla1 - lat) / res), int((lon - blo) / res)
        if 0 <= i < WC.shape[0] and 0 <= j < WC.shape[1]:
            c = CLS.get(int(WC[i, j]))
            if c: cnt[c] = cnt.get(c, 0) + 1
    tot = sum(cnt.values()) or 1
    return {k: round(100 * v / tot) for k, v in cnt.items() if v}

# ---------- land cover for every Montenegrin hex ----------
lc = {}
for (q, r), h in known.items():
    if h['terrain'] in ('sea', 'lake'): continue
    lc[f'{q},{r}'] = cover(*center(q, r))
print('land cover hexes', len(lc))

# ---------- context ring: sea and neighbouring countries ----------
ring = country.buffer(42000)
ctx = []
nr0, nr1 = int((ring.bounds[1] - miny) / H) - 2, int((ring.bounds[3] - miny) / H) + 2
for r in range(nr0, nr1):
    for q in range(int((ring.bounds[0] - minx) / W - r / 2) - 2, int((ring.bounds[2] - minx) / W - r / 2) + 3):
        if (q, r) in known: continue
        x, y = center(q, r)
        p = Point(x, y)
        if not ring.contains(p): continue
        lon, lat = to_ll.transform(x, y)
        if not (lon0 < lon < lon1 and lat0 < lat < lat1): continue
        pts = [(x + math.cos(a) * R * .7, y + math.sin(a) * R * .7) for a in np.linspace(0, 2 * math.pi, 7)[:-1]] + [(x, y)]
        el = [elev(*to_ll.transform(a, b)) for a, b in pts]
        em = float(np.mean(el))
        ec = elev(lon, lat)
        if skadar.contains(p): kind = 'lake'
        elif (em < 1 and max(el) < 6) or ec < 0.5: kind = 'sea'
        else: kind = 'land'
        rec = dict(q=q, r=r, k=kind, e=round(em), x=round(max(el) - min(el)))
        if kind == 'land': rec['lc'] = cover(x, y)
        ctx.append(rec)
print('context hexes', len(ctx), {k: sum(c['k'] == k for c in ctx) for k in ('sea', 'land', 'lake')})

# ---------- rivers ----------
MAJOR = {'Morača': 3, 'Tara': 3, 'Lim': 3, 'Лим': 3, 'Piva': 3, 'Drina': 3, 'Bojana': 3, 'Buna': 3, 'Zeta': 2, 'Ćehotina': 2,
         'Cijevna': 2, 'Ibar': 2, 'Komarnica': 2, 'Crnojevića rijeka': 2, 'Rijeka Crnojevića': 2, 'Ribnica': 2, 'Drini': 2, 'Uvac': 2,
         'Увац': 2, 'Trebišnjica': 2, 'Grnčar': 2, 'Ljuča': 2, 'Bistrica': 1, 'Mrtvica': 1, 'Sitnica': 1, 'Vezišnica': 1}
osm = json.load(open(os.path.join(RAW, 'osm_rivers.json')))
groups = {}
for e in osm['elements']:
    if 'geometry' not in e: continue
    nm = e.get('tags', {}).get('name') or e.get('tags', {}).get('name:sr-Latn') or ''
    line = LineString([to_utm.transform(p['lon'], p['lat']) for p in e['geometry']])
    groups.setdefault(nm, []).append(line)
view = country.buffer(45000)
rivers = []
for nm, ls in groups.items():
    u = unary_union(ls)
    merged = linemerge(u) if u.geom_type == 'MultiLineString' else u
    parts = list(merged.geoms) if hasattr(merged, 'geoms') else [merged]
    rank = MAJOR.get(nm, 0)
    for g in parts:
        g = g.intersection(view)
        if g.is_empty: continue
        for seg in (list(g.geoms) if hasattr(g, 'geoms') else [g]):
            if seg.geom_type != 'LineString': continue
            if seg.length < (4000 if rank else 9000): continue
            seg = seg.simplify(220)
            inside = seg.intersection(country).length / seg.length > .5
            rivers.append(dict(n=nm, w=rank, cg=int(inside), p=[unit(x, y) for x, y in seg.coords]))
print('river segments', len(rivers), 'major', sum(r['w'] >= 2 for r in rivers))

# ---------- municipal label anchors (pole of inaccessibility approx: largest inner point) ----------
labels = []
for _, row in mb.iterrows():
    nm = row['name'].replace('Opština ', '').replace('Glavni grad ', '').replace('Prijestolnica ', '').split(' - ')[0].strip()
    g = row.geometry
    best, bd = None, -1
    minx2, miny2, maxx2, maxy2 = g.bounds
    for xx in np.linspace(minx2, maxx2, 25):
        for yy in np.linspace(miny2, maxy2, 25):
            p = Point(xx, yy)
            if g.contains(p):
                d = g.exterior.distance(p) if g.geom_type == 'Polygon' else min(pp.exterior.distance(p) for pp in g.geoms)
                if d > bd: best, bd = (xx, yy), d
    labels.append(dict(n=nm, p=unit(*best), a=round(g.area / 1e6)))

json.dump(dict(lc=lc, ctx=ctx, rivers=rivers, labels=labels,
               src='Pokrivač tla: ESA WorldCover 2021 (10 m), uzorak 61 tačka po heksu. Rijeke: OpenStreetMap. Okolne zemlje i more: reljef Terrarium.'),
          open(os.path.join(BUILD, 'cgviz.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('wrote', os.path.getsize(os.path.join(BUILD, 'cgviz.json')))
