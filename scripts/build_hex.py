"""Build the CG Civ hex map: real data reconciled onto a ~3 km hex grid.
Output: build/cgciv.json (consumed by site/index.html)."""
import json, math, os, glob, re
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from PIL import Image
from pyproj import Transformer

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
BUILD = os.path.join(HERE, '..', 'build')
R = 1750.0                      # hex circumradius in metres (flat-to-flat ~3.03 km, area ~7.96 km2)
W, H = math.sqrt(3) * R, 1.5 * R
UTM = 'EPSG:32634'
to_utm = Transformer.from_crs('EPSG:4326', UTM, always_xy=True)
to_ll = Transformer.from_crs(UTM, 'EPSG:4326', always_xy=True)

stats = json.load(open(os.path.join(BUILD, 'muni_stats.json')))
M = stats['munis']
MUNIS = list(M.keys())

def muni_name(raw):
    s = raw.replace('Opština ', '').replace('Glavni grad ', '').replace('Prijestolnica ', '')
    return s.split(' - ')[0].strip()

# ---------- boundaries ----------
kb = gpd.read_file(os.path.join(RAW, 'kontur.gpkg'))
mb = kb[kb.admin_level == 6].copy()
mb['muni'] = mb['name'].map(muni_name)
assert set(mb.muni) == set(MUNIS), set(mb.muni) ^ set(MUNIS)
mb = mb.to_crs(UTM)
country = unary_union(mb.geometry)
lakes = gpd.read_file(os.path.join(RAW, 'ne_lakes.geojson'))
skadar = lakes[lakes['name'] == 'Lake Skadar'].to_crs(UTM).geometry.iloc[0]

# ---------- DEM mosaic (terrarium z10) ----------
Z = 10
tiles = glob.glob(os.path.join(RAW, 'dem', f'{Z}_*.png'))
xs = sorted({int(os.path.basename(t).split('_')[1]) for t in tiles})
ys = sorted({int(os.path.basename(t).split('_')[2].split('.')[0]) for t in tiles})
mos = np.zeros((len(ys) * 256, len(xs) * 256), dtype=np.float32)
for t in tiles:
    _, x, y = os.path.basename(t)[:-4].split('_')
    a = np.asarray(Image.open(t).convert('RGB')).astype(np.float32)
    e = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    i, j = ys.index(int(y)), xs.index(int(x))
    mos[i * 256:(i + 1) * 256, j * 256:(j + 1) * 256] = e

def elev(lon, lat):
    n = 2 ** Z
    px = (lon + 180) / 360 * n * 256 - xs[0] * 256
    py = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * 256 - ys[0] * 256
    return float(mos[int(py), int(px)])

# ---------- hex grid ----------
minx, miny, maxx, maxy = country.buffer(9000).bounds
def center(q, r):  # pointy-top axial -> xy
    return (minx + W * (q + r / 2), miny + H * r)
def axial(x, y):
    r = (y - miny) / H
    q = (x - minx) / W - r / 2
    # cube rounding
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds: rq = -rr - rs
    elif dr > ds: rr = -rq - rs
    return int(rq), int(rr)

nr = int((maxy - miny) / H) + 2
hexes = {}
coast_zone = country.buffer(7000)
mpoly = list(zip(mb.muni, mb.geometry))
for r in range(nr):
    for q in range(-r // 2 - 2, int((maxx - minx) / W) + 3):
        x, y = center(q, r)
        if x < minx - W or x > maxx + W: continue
        p = Point(x, y)
        if not coast_zone.contains(p): continue
        lon, lat = to_ll.transform(x, y)
        ring = [(x + dx * R * .55, y + dy * R * .55) for dx, dy in [(0, 0), (1, 0), (-1, 0), (.5, .87), (-.5, .87), (.5, -.87), (-.5, -.87)]]
        ring += [(x + math.cos(a) * R * .9, y + math.sin(a) * R * .9) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        el = [elev(*to_ll.transform(a, b)) for a, b in ring]
        mu = None
        if country.contains(p):
            for name, g in mpoly:
                if g.contains(p): mu = name; break
        in_lake = skadar.contains(p)
        if mu and np.mean(el) < -1 and np.max(el) < 8: mu = None   # Boka and other inner sea waters inside the boundary
        if mu is None:
            if np.mean(el) > 2 and not in_lake: continue      # foreign land: not drawn
            kind = 'lake' if in_lake else 'sea'
        else:
            kind = 'lake' if in_lake else 'land'
        hexes[(q, r)] = dict(q=q, r=r, x=x, y=y, lon=lon, lat=lat, muni=mu, kind=kind,
                             emean=float(np.mean(el)), emax=float(np.max(el)), emin=float(np.min(el)))
print('hexes', len(hexes), 'land', sum(h['kind'] == 'land' for h in hexes.values()))

NB = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
def neighbors(h):
    return [hexes.get((h['q'] + a, h['r'] + b)) for a, b in NB]

# terrain from relief (derived; no land-cover layer)
for h in hexes.values():
    if h['kind'] != 'land': h['terrain'] = h['kind']; continue
    relief = h['emax'] - h['emin']; e = h['emean']
    if h['emax'] > 2100: t = 'peak'
    elif e > 1350 or relief > 750: t = 'mountain'
    elif e > 650 or relief > 450: t = 'hills'
    elif e < 120 and relief < 120: t = 'plains'
    else: t = 'grassland'
    h['terrain'] = t
    h['coast'] = any(n and n['kind'] == 'sea' for n in neighbors(h))
    h['lakeside'] = any(n and n['kind'] == 'lake' for n in neighbors(h))

def hex_of(lon, lat):
    x, y = to_utm.transform(lon, lat)
    k = axial(x, y)
    h = hexes.get(k)
    if h is None or h['kind'] == 'sea':  # snap to nearest land hex (coastal points)
        best, bd = None, 1e18
        for a, b in NB + [(0, 0)]:
            c = hexes.get((k[0] + a, k[1] + b))
            if c and c['kind'] != 'sea':
                d = (c['x'] - x) ** 2 + (c['y'] - y) ** 2
                if d < bd: best, bd = c, d
        h = best or h
    return h

# ---------- population (Kontur H3 2023, scaled to Census 2023 per municipality) ----------
kp = gpd.read_file(os.path.join(RAW, 'kpop.gpkg')).to_crs('EPSG:4326')
for h in hexes.values(): h['pop_raw'] = 0.0
for g, pop in zip(kp.geometry, kp.population):
    c = g.centroid; h = hex_of(c.x, c.y)
    if h and h['muni']: h['pop_raw'] += pop
for m in MUNIS:
    hs = [h for h in hexes.values() if h['muni'] == m]
    tot = sum(h['pop_raw'] for h in hs)
    for h in hs:
        h['pop'] = round(M[m]['pop2023'] * h['pop_raw'] / tot) if tot else 0

# ---------- point layers ----------
def load(n): return json.load(open(os.path.join(RAW, n)))
def add_points(rows, key, getlonlat=lambda r: (r['lon'], r['lat']), w=lambda r: 1):
    for h in hexes.values(): h.setdefault(key, 0)
    for r in rows:
        lon, lat = getlonlat(r); h = hex_of(lon, lat)
        if h: h[key] += w(r)
osm_ll = lambda e: (e['lon'], e['lat']) if 'lon' in e else (e['center']['lon'], e['center']['lat'])
worship = [e for e in load('osm_worship.json')['elements'] if 'lon' in e or 'center' in e]
tour = [e for e in load('osm_tour.json')['elements'] if 'lon' in e or 'center' in e]
lodging = [e for e in tour if e['tags'].get('tourism') in ('hotel', 'guest_house', 'apartment', 'hostel')]
heritage = [e for e in tour if e['tags'].get('historic') or e['tags'].get('tourism') == 'museum']
add_points(worship, 'worship', osm_ll)
add_points(lodging, 'lodging', osm_ll)
add_points(heritage, 'heritage', osm_ll)

# ---------- municipal totals distributed onto hexes ----------
def spread(field, weight, out):
    for m in MUNIS:
        v = M[m].get(field)
        hs = [h for h in hexes.values() if h['muni'] == m]
        tw = sum(weight(h) for h in hs)
        for h in hs:
            h[out] = (v or 0) * weight(h) / tw if tw else 0
spread('nights2024', lambda h: h['lodging'] * 3 + h['pop'] / 1000, 'nights')
spread('firms2025', lambda h: h['pop'], 'firms')
spread('higher_ed', lambda h: h['pop'], 'higher')
for m in MUNIS:
    M[m]['wagebill_meur'] = M[m]['employed2024'] * M[m]['net_wage2025'] * 12 / 1e6
spread('wagebill_meur', lambda h: h['pop'], 'wagebill')

# ---------- power plants (Wikidata capacities) ----------
power = [p for p in load('wd_power.json') if p.get('cap')]
for h in hexes.values(): h['mw'] = 0
for p in power:
    h = hex_of(p['lon'], p['lat']); h['mw'] += float(p['cap'])

# ---------- Civ yields ----------
BASE = {'plains': (2, 1), 'grassland': (2, 0), 'hills': (1, 1), 'mountain': (0, 1), 'peak': (0, 0), 'lake': (2, 0), 'sea': (1, 0)}
for h in hexes.values():
    f, p = BASE[h['terrain']]
    if h.get('coast'): f += 1
    if h.get('lakeside'): f += 1
    h['food'] = f
    h['prod'] = p + round(h.get('firms', 0) / 60) + round(h['mw'] / 20)
    h['gold'] = round(h.get('wagebill', 0), 1)               # 1 zlato = 1 mil. € neto zarada godišnje
    h['science'] = round(h.get('higher', 0) / 300)
    h['culture'] = h['heritage'] + round(h.get('nights', 0) / 25000)
    h['faith'] = h['worship']

# ---------- cities (municipal seats) ----------
SEATS = {'Podgorica': (19.2594, 42.4304), 'Nikšić': (18.9445, 42.7731), 'Bar': (19.1003, 42.0931), 'Bijelo Polje': (19.7476, 43.0384),
         'Herceg Novi': (18.5375, 42.4531), 'Berane': (19.8732, 42.8425), 'Pljevlja': (19.3584, 43.3567), 'Budva': (18.8403, 42.2864),
         'Rožaje': (20.1665, 42.8410), 'Kotor': (18.7712, 42.4247), 'Ulcinj': (19.2183, 41.9294), 'Cetinje': (18.9142, 42.3911),
         'Danilovgrad': (19.1000, 42.5536), 'Tivat': (18.6961, 42.4350), 'Zeta': (19.2347, 42.3653), 'Tuzi': (19.3317, 42.3656),
         'Plav': (19.9456, 42.5967), 'Kolašin': (19.5222, 42.8222), 'Mojkovac': (19.5833, 42.9600), 'Petnjica': (19.9644, 42.9089),
         'Gusinje': (19.8339, 42.5619), 'Andrijevica': (19.7919, 42.7339), 'Žabljak': (19.1233, 43.1542), 'Plužine': (18.8394, 43.1528),
         'Šavnik': (19.0967, 42.9564)}
nat = {k: sum((M[m].get(k) or 0) for m in MUNIS) for k in ['pop2023', 'employed2024', 'unemployed_jan2026', 'higher_ed', 'pop15plus',
                                                             'nights2024', 'students2024', 'firms2025', 'firms2024', 'dwellings', 'dwellings_seasonal', 'wagebill_meur']}
nat['net_wage2025'] = 1012   # MONSTAT, prosječna neto zarada CG 2025 (saopštenje 8/2026)
nat['higher_share'] = nat['higher_ed'] / nat['pop15plus']
nat['prog_pct'] = 11.33

famous = load('wd_famous.json')
BAD = re.compile(r'river|watercourse|language|^region$|sea\b|basin|meridian|organization|order|outbreak|shooting|orogenic|railway line', re.I)
wonders = []
for f in famous:
    if BAD.search(f['types']) or not f['types']: continue
    x, y = to_utm.transform(f['lon'], f['lat'])
    if not country.buffer(15000).contains(Point(x, y)): continue
    if any(w['name'] == f['name'] for w in wonders): continue
    wonders.append(f)
wonders = wonders[:20]
RENAME = {'National Museum of Montenegro': 'Narodni muzej Crne Gore', 'Zračna luka Tivat': 'Aerodrom Tivat'}
for w in wonders: w['name'] = RENAME.get(w['name'], w['name'])
for w in wonders:
    h = hex_of(w['lon'], w['lat'])
    if h is None or h['kind'] == 'sea' and w['name'] != 'Boka Kotorska':
        x, y = to_utm.transform(w['lon'], w['lat'])
        h = min((c for c in hexes.values() if c['kind'] != 'sea'), key=lambda c: (c['x'] - x) ** 2 + (c['y'] - y) ** 2)
    w['q'], w['r'] = h['q'], h['r']
    px = Point(*to_utm.transform(w['lon'], w['lat']))
    w['muni'] = next((n for n, g in mpoly if g.contains(px)), h['muni']) or 'more'

PORT_MUNIS = {'Bar', 'Kotor', 'Herceg Novi'}
MARINA = {'Tivat', 'Budva', 'Bar', 'Kotor', 'Herceg Novi'}
AIRPORT = {'Zeta', 'Tivat'}
UNI = {'Podgorica'}
NP = {'Žabljak': 'Durmitor', 'Plužine': 'Durmitor', 'Šavnik': 'Durmitor', 'Kolašin': 'Biogradska gora', 'Mojkovac': 'Biogradska gora',
      'Berane': 'Biogradska gora', 'Cetinje': 'Lovćen', 'Budva': 'Lovćen', 'Kotor': 'Lovćen', 'Bar': 'Skadarsko jezero',
      'Podgorica': 'Skadarsko jezero', 'Zeta': 'Skadarsko jezero', 'Plav': 'Prokletije', 'Gusinje': 'Prokletije',
      'Andrijevica': 'Prokletije'}

cities = []
for m in MUNIS:
    s = M[m]; lon, lat = SEATS[m]; h = hex_of(lon, lat)
    hs = [x for x in hexes.values() if x['muni'] == m]
    d = []  # districts: (name, rule)
    sp = (s['students2024'] or 0) / s['pop2023'] * 1000; nsp = nat['students2024'] / nat['pop2023'] * 1000
    if m in UNI or sp >= nsp * 1.15: d.append(('Kampus', f'studenti na 1.000 stanovnika {sp:.0f} (CG {nsp:.0f})' + ('; sjedište UCG' if m in UNI else '')))
    if s['net_wage2025'] >= nat['net_wage2025']: d.append(('Trgovački centar', f"neto plata {s['net_wage2025']} € ≥ CG {nat['net_wage2025']} €"))
    fp = s['firms2025'] / s['pop2023'] * 1000; nfp = nat['firms2025'] / nat['pop2023'] * 1000
    if fp >= nfp * 1.3: d.append(('Berza i preduzetništvo', f'{fp:.0f} aktivnih firmi na 1.000 stanovnika (CG {nfp:.0f})'))
    if m in PORT_MUNIS: d.append(('Luka', 'luka u MONSTAT tabeli 28-14 (2024)'))
    npc = (s.get('nights2024') or 0) / s['pop2023']
    if npc >= 20: d.append(('Ljetovalište', f'{npc:.0f} noćenja po stanovniku 2024'))
    mw = sum(x['mw'] for x in hs)
    if mw >= 100: d.append(('Industrijska zona', f'elektrane {mw:.0f} MW (Wikidata)'))
    her = sum(x['heritage'] for x in hs)
    if her >= 60: d.append(('Pozorišni trg', f'{her} objekata baštine u OSM'))
    wo = sum(x['worship'] for x in hs)
    if wo / s['pop2023'] * 1000 >= 6: d.append(('Sveto mjesto', f'{wo} bogomolja u OSM'))
    if m in AIRPORT: d.append(('Aerodrom', 'međunarodni aerodrom na teritoriji opštine'))
    if m == 'Podgorica': d.append(('Vladin trg', 'Glavni grad'))
    if m == 'Cetinje': d.append(('Prijestonica', 'prijestonica po Ustavu'))
    sea = (s.get('dwellings_seasonal') or 0) / s['dwellings'] * 100
    if sea >= 35: d.append(('Kvart vikendica', f'{sea:.0f}% stanova za sezonsko korišćenje'))
    if m in NP: d.append(('Rezervat', f'nacionalni park {NP[m]}'))
    labour = s['employed2024'] + s['unemployed_jan2026']
    he = s['higher_ed'] / s['pop15plus']
    cities.append(dict(
        name=m, q=h['q'], r=h['r'], lon=lon, lat=lat, pop=s['pop2023'], pop1991=s.get('pop1991'), pop2011=s.get('pop2011'), districts=[{'n': a, 'why': b} for a, b in d],
        food=sum(x['food'] for x in hs), prod=sum(x['prod'] for x in hs), gold=round(s['wagebill_meur'], 1),
        science=sum(x['science'] for x in hs), culture=sum(x['culture'] for x in hs), faith=sum(x['faith'] for x in hs),
        hexes=len(hs), area_km2=round(len(hs) * 7.96),
        citizens=dict(higher_share=round(he * 100, 1), one_in=round(1 / he, 1) if he else None,
                      nat_one_in=round(1 / nat['higher_share'], 1), prog=s['programming_pct'],
                      unemp_share=round(s['unemployed_jan2026'] / labour * 100, 1),
                      age65=round(s['age65plus'] / s['pop2023'] * 100, 1), age0_14=round(s['age0_14'] / s['pop2023'] * 100, 1)),
    ))

# ---------- municipal indicator table (Explorer + lenses) ----------
def per(a, b, k=1): return round(a / b * k, 2) if a is not None and b else None
table = []
for m in MUNIS:
    s = M[m]
    table.append({
        'Opština': m,
        'Stanovnici 2023': s['pop2023'],
        'Promjena 1991-2023 %': per(s['pop2023'] - s['pop1991'], s['pop1991'], 100) if s.get('pop1991') else None,
        'Gustina st/km2': per(s['pop2023'], len([h for h in hexes.values() if h['muni'] == m]) * 7.96),
        'Neto plata 2025 €': s['net_wage2025'],
        'Masa zarada mil. €': round(s['wagebill_meur'], 1),
        'Zaposleni 2024': s['employed2024'],
        'Zaposleni na 100 st.': per(s['employed2024'], s['pop2023'], 100),
        'Nezaposleni 1/2026': s['unemployed_jan2026'],
        'Nezaposlenost % (reg.)': per(s['unemployed_jan2026'], s['employed2024'] + s['unemployed_jan2026'], 100),
        'Firme 2025': s['firms2025'],
        'Firme na 1.000 st.': per(s['firms2025'], s['pop2023'], 1000),
        'Rast firmi 2024-25 %': per(s['firms2025'] - s['firms2024'], s['firms2024'], 100),
        'Fakultet % (15+)': per(s['higher_ed'], s['pop15plus'], 100),
        'Programiranje %': s['programming_pct'],
        'Studenti na 1.000 st.': per(s['students2024'], s['pop2023'], 1000),
        'Noćenja 2024': s.get('nights2024'),
        'Noćenja po stanovniku': per(s.get('nights2024'), s['pop2023']),
        'Sezonski stanovi %': per(s['dwellings_seasonal'], s['dwellings'], 100),
        'Prirodni priraštaj ‰': s['natural_increase_rate'],
        '65+ %': per(s['age65plus'], s['pop2023'], 100),
        '0-14 %': per(s['age0_14'], s['pop2023'], 100),
        'Ljekari na 10.000 st.': per(s.get('physicians'), s['pop2023'], 10000),
        'MOP korisnici na 1.000 st.': per(s['welfare_members'], s['pop2023'], 1000),
        'Bogomolje (OSM)': sum(h['worship'] for h in hexes.values() if h['muni'] == m),
        'Smještaj (OSM objekti)': sum(h['lodging'] for h in hexes.values() if h['muni'] == m),
    })

out = {
    'meta': {'hexR_m': R, 'hex_km2': 7.96, 'built': '2026-11-26', 'nat': nat},
    'hexes': [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in h.items()
               if k in ('q', 'r', 'lon', 'lat', 'muni', 'terrain', 'coast', 'emean', 'emax', 'pop', 'food', 'prod', 'gold', 'science', 'culture',
                        'faith', 'mw', 'lodging', 'heritage', 'worship', 'nights')} for h in hexes.values()],
    'cities': cities, 'wonders': [{k: w[k] for k in ('name', 'q', 'r', 'muni', 'sitelinks', 'types', 'id')} for w in wonders],
    'power': [{'name': p['name'], 'mw': float(p['cap']), **dict(zip(('q', 'r'), (hex_of(p['lon'], p['lat'])['q'], hex_of(p['lon'], p['lat'])['r'])))} for p in power],
    'table': table, 'sources': stats['sources'],
}
for h in out['hexes']:
    h['nights'] = round(h.get('nights', 0)); h.setdefault('pop', 0); h.setdefault('gold', 0)
json.dump(out, open(os.path.join(BUILD, 'cgciv.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('pop check', sum(h['pop'] for h in out['hexes']), 'gold', round(sum(h['gold'] for h in out['hexes'])), 'wonders', [w['name'] for w in wonders])
print('size KB', os.path.getsize(os.path.join(BUILD, 'cgciv.json')) // 1024)
