"""Visual layers for the CG Civ map: land cover per hex (ESA WorldCover 2021),
a ring of context hexes (Adriatic and neighbouring countries) and rivers (OSM).
Output: build/cgviz.json, coordinates in the site's hex units (R = 1)."""
import json, math, os, glob, re
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

# ---------- sveta mjesta (Wikidata, rang po broju Wikipedia jezika) ----------
REN = {"Pasha's Mosque": 'Pašina džamija (Ulcinj)', "Seaman's Mosque": 'Pomorska džamija (Ulcinj)', 'Bregu Mosque': 'Džamija na Bregu (Ulcinj)',
       'Kryepazari Mosque': 'Džamija Kriepazari (Ulcinj)', 'Lami Mosque': 'Lamina džamija (Ulcinj)', 'Namazgjahu Mosque': 'Namazdžah (Ulcinj)',
       'Church-Mosque of Ulcinj': 'Crkva-džamija (Ulcinj)', 'Church of the Holy Heart of Jesus': 'Crkva Srca Isusova (Podgorica)',
       'Holy Trinity monastery ( Pljevlja )': 'Manastir Sveta Trojica (Pljevlja)', 'Church of Our Lady of Remedy': 'Crkva Gospe od Zdravlja (Kotor)',
       'Church of Saint Luke in Kotor': 'Crkva Svetog Luke (Kotor)', 'Serbian Orthodox church of St Nicolas in Kotor': 'Crkva Svetog Nikole (Kotor)',
       'Saint Anne (Kotor)': 'Crkva Svete Ane (Kotor)', 'Katedrala Bezgrešnog začeća Blažene Djevice Marije na Gretvi, Stari Bar': 'Katedrala na Gretvi (Bar)',
       'Njegošev mauzolej': 'Lovćen: Njegoševa kapela i mauzolej', 'Dovolja Monastery': 'Manastir Dovolja', 'Church of the Holy Savior': 'Crkva Svetog Spasa',
       'Đurđevića Tara Monastery': 'Manastir Đurđevića Tara', 'Podmalinsko Monastery': 'Manastir Podmalinsko', 'Majstorovina Monastery': 'Manastir Majstorovina',
       'Church of St. Ivan': 'Crkva Svetog Ivana', 'Saint Michael the Archangel church in Herceg Novi': 'Crkva Svetog Arhanđela Mihaila (Herceg Novi)',
       'Saints Peter and Paul Orthodox church in Risan': 'Crkva Svetih Petra i Pavla (Risan)', 'Church of St. Jerome in Herceg Novi': 'Crkva Svetog Jeronima (Herceg Novi)',
       'Church of Saints Peter and Paul, Bijelo Polje': 'Crkva Svetih Petra i Pavla (Bijelo Polje)', 'St. John the Baptist Church in Zaton': 'Crkva Svetog Jovana Krstitelja (Zaton)',
       'St. Mary Church': 'Crkva Svete Marije', 'Royal Tomb in Cetinje': 'Kraljevska grobnica (Cetinje)', 'St. Michael church in Kotor': 'Crkva Svetog Mihaila (Kotor)',
       'St Elijah Church': 'Crkva Svetog Ilije'}
NOTE = {'Q13424615': 'Jezerski vrh, 1.657 m. Njegoš je 1845. podigao kapelu posvećenu Svetom Petru Cetinjskom i u njoj tražio da bude sahranjen; prenesen je 1855. Kapela je razorena 1916, obnovljena između dva rata, srušena 1972; Meštrovićev mauzolej otvoren je 1974.',
        'Q1257434': 'Manastir u stijeni iz 17. vijeka, jedno od najposjećenijih hodočasničkih mjesta na Balkanu.', 'Q770580': 'Osnovan 1484; čuva mošti Svetog Petra Cetinjskog.'}
def kind(r):
    t, rl = r['types'].lower(), r['rel'].lower()
    if 'mausoleum' in t: return 'memorial'
    if 'mosque' in t and 'catholic' not in t: return 'islam'
    if 'islam' in rl: return 'islam'
    if 'catholic' in rl or 'catholic' in t or 'abbey' in t or r['id'] in ('Q5117907', 'Q4981066', 'Q12758206', 'Q65133683', 'Q136236545'): return 'catholic'
    return 'orthodox'
HOLY_STAR = {'Q1257434', 'Q770580', 'Q13424615', 'Q966429', 'Q1639036', 'Q658743', 'Q1395885'}
holy, seen = [], set()
for r in json.load(open(os.path.join(RAW, 'wd_holy.json'))):
    if r['id'] in seen: continue
    seen.add(r['id'])
    x, y = to_utm.transform(r['lon'], r['lat']); p = Point(x, y)
    mu = next((nm for nm, g in [(row['name'].replace('Opština ', '').replace('Glavni grad ', '').replace('Prijestolnica ', '').split(' - ')[0].strip(), row.geometry) for _, row in mb.iterrows()] if g.buffer(1500).contains(p)), None)
    if not mu or re.match(r'^Q\d+$', r['name']): continue
    holy.append(dict(id=r['id'], n=REN.get(r['name'], r['name']), k=kind(r), sl=r['sitelinks'], m=mu, p=unit(x, y), star=int(r['id'] in HOLY_STAR), note=NOTE.get(r['id'], '')))
holy.sort(key=lambda h: (-h['star'], -h['sl']))
print('holy', len(holy), [(h['n'], h['k'], h['sl']) for h in holy[:10]])

# ---------- obala i Boka u finoj rezoluciji (Terrarium z12, ~28 m) ----------
from scipy import ndimage
Z2 = 12; n12 = 2 ** Z2
t12 = glob.glob(os.path.join(RAW, 'dem12', '*.png'))
x12 = sorted({int(os.path.basename(t).split('_')[1]) for t in t12}); y12 = sorted({int(os.path.basename(t).split('_')[2][:-4]) for t in t12})
m12 = np.full((len(y12) * 256, len(x12) * 256), 50, dtype=np.float32)
for t in t12:
    _, xx, yy = os.path.basename(t)[:-4].split('_')
    a = np.asarray(Image.open(t).convert('RGB')).astype(np.float32)
    m12[y12.index(int(yy)) * 256:(y12.index(int(yy)) + 1) * 256, x12.index(int(xx)) * 256:(x12.index(int(xx)) + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
def e12(lon, lat):
    px = (np.asarray(lon) + 180) / 360 * n12 * 256 - x12[0] * 256
    py = (1 - np.arcsinh(np.tan(np.radians(np.asarray(lat)))) / np.pi) / 2 * n12 * 256 - y12[0] * 256
    return m12[np.clip(py.astype(int), 0, m12.shape[0] - 1), np.clip(px.astype(int), 0, m12.shape[1] - 1)]
# raster u heks jedinicama, 50 m po pikselu, za obalni pojas
RES = 50.0
X0, Y0 = to_utm.transform(18.42, 42.57); X1, Y1 = to_utm.transform(19.44, 41.85)
xs_ = np.arange(X0, X1, RES); ys_ = np.arange(Y0, Y1, -RES)
GX, GY = np.meshgrid(xs_, ys_)
LON, LAT = to_ll.transform(GX, GY)
EL = e12(LON, LAT)
water = EL < 0.5
water = ndimage.binary_opening(water, iterations=1)
# Skadarsko jezero i kopnena jezera nijesu more: samo voda povezana sa otvorenim morem
lab, nl = ndimage.label(water)
sea_lab = np.bincount(lab[-1, :][lab[-1, :] > 0]).argmax() if (lab[-1, :] > 0).any() else 0
sea = lab == sea_lab
dist = ndimage.distance_transform_edt(sea) * RES        # m od obale
img = np.zeros(sea.shape + (4,), dtype=np.uint8)
t = np.clip(dist / 2500, 0, 1)
shallow, deep = np.array([52, 140, 156]), np.array([30, 96, 128])
col = shallow[None, None, :] * (1 - t[..., None]) + deep[None, None, :] * t[..., None]
foam = sea & (dist <= RES * 1.01)
col[foam] = [205, 236, 232]
img[..., :3] = col.astype(np.uint8)
alpha = np.where(sea, np.clip((5200 - dist) / 2000, 0, 1) * 255, 0)
img[..., 3] = alpha.astype(np.uint8)
Image.fromarray(img, 'RGBA').save(os.path.join(HERE, '..', 'site', 'obala.png'), optimize=True)
coast = dict(x=round((X0 - minx) / R, 4), y=round(-(Y0 - miny) / R, 4), w=round(len(xs_) * RES / R, 4), h=round(len(ys_) * RES / R, 4))
print('obala.png', img.shape, os.path.getsize(os.path.join(HERE, '..', 'site', 'obala.png')))

# kopnena državna granica (bez obale), precizna linija iz Kontur granica
ext = country if country.geom_type == 'Polygon' else max(country.geoms, key=lambda g: g.area)
pts = list(ext.exterior.coords)
lon_, lat_ = to_ll.transform(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
near = np.zeros(len(pts), bool)
for dx, dy in [(0, 0), (200, 0), (-200, 0), (0, 200), (0, -200), (140, 140), (-140, -140), (140, -140), (-140, 140)]:
    lo2, la2 = to_ll.transform(np.array([p[0] + dx for p in pts]), np.array([p[1] + dy for p in pts]))
    inside = (lo2 > 18.42) & (lo2 < 19.44) & (la2 > 41.85) & (la2 < 42.57)
    near |= inside & (e12(lo2, la2) < 0.5)
border, cur = [], []
for (x, y), c in zip(pts, near):
    if not c: cur.append((x, y))
    elif cur:
        if len(cur) > 2: border.append(cur)
        cur = []
if len(cur) > 2: border.append(cur)
border = [[unit(x, y) for x, y in LineString(b).simplify(40).coords] for b in border]
print('kopnena granica', len(border), sum(len(b) for b in border))

def U(lon, lat): return unit(*to_utm.transform(lon, lat))
countries = [dict(n='HRVATSKA', p=U(18.33, 42.6)), dict(n='BOSNA I HERCEGOVINA', p=U(18.45, 43.2)), dict(n='SRBIJA', p=U(19.95, 43.35)),
             dict(n='KOSOVO', p=U(20.45, 42.72)), dict(n='ALBANIJA', p=U(19.75, 42.15)), dict(n='JADRANSKO MORE', p=U(18.85, 42.0))]
prevlaka = dict(n='Prevlaka', p=U(18.5372, 42.3958),
    note='Po Privremenom protokolu iz 2002. kopneni dio poluostrva i pojas mora na ulazu u Boku od oko 550 m pripadaju Hrvatskoj, a dio akvatorija uz poluostrvo nije razgraničen. Crna Gora smatra pitanje granice na kopnu i moru otvorenim; konačno razgraničenje nije završeno.')

json.dump(dict(lc=lc, ctx=ctx, rivers=rivers, labels=labels, holy=holy, coast=coast, border=border, countries=countries, prevlaka=prevlaka,
               src='Pokrivač tla: ESA WorldCover 2021 (10 m), uzorak 61 tačka po heksu. Rijeke: OpenStreetMap. Okolne zemlje i more: reljef Terrarium.'),
          open(os.path.join(BUILD, 'cgviz.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('wrote', os.path.getsize(os.path.join(BUILD, 'cgviz.json')))
