"""Newer data (stanje 26.11.2026): tourism total 2025, hotel nights Aug+Sep 2026 vs 2025, unemployed 30.6.2026, natural increase 2025."""
import pdfplumber, re, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from extract_stats import MUNIS, NORM, norm, rows
RAW = os.path.join(os.path.dirname(__file__), '..', 'raw'); OUT = os.path.join(os.path.dirname(__file__), '..', 'build', 'update2026.json')
NORM['h. novi'] = 'Herceg Novi'
def tour(pdf, page):  # -> {muni: (arrivals_total, nights_total)}
    res = {}
    for m, label, vals, texts in rows(pdf, page):
        m = m or NORM.get(norm(label))
        if m and len(vals) >= 7 and vals[2] is not None: res[m] = (vals[2], vals[6])
    return res
t25 = tour('tur2025.pdf', 2); h26 = [tour('t26_8.pdf', 1), tour('t26_9.pdf', 1)]; h25 = [tour('t25_8.pdf', 1), tour('t25_9b.pdf', 1)]
un = {}
for line in pdfplumber.open(os.path.join(RAW, 'zzz_pol26.pdf')).pages[4].extract_text().split('\n') + pdfplumber.open(os.path.join(RAW, 'zzz_pol26.pdf')).pages[5].extract_text().split('\n'):
    mm = re.match(r'\d+ (.+?) (\d+) (\d+) (\d+) ([\d.]+) ', line)
    if mm and NORM.get(norm(mm.group(1))): un[NORM[norm(mm.group(1))]] = {'unemp': int(mm.group(2)), 'reg_employed': int(mm.group(3)), 'rate': float(mm.group(5))}
# MONSTAT saopštenje 59/2026 (13.05.2026), tab. 3 - stope prirodnog priraštaja 2025, preuzeto iz istraživačkog izvještaja (PDF nije dostupan iz kontejnera)
NI25 = {'Andrijevica': -8.7, 'Bar': 2.8, 'Berane': -2.3, 'Bijelo Polje': -2.8, 'Budva': 5.5, 'Cetinje': -5.1, 'Danilovgrad': -2.4, 'Gusinje': -3.3,
        'Herceg Novi': -2.3, 'Kolašin': -3.9, 'Kotor': -0.8, 'Mojkovac': -5.4, 'Nikšić': -1.2, 'Petnjica': -4.9, 'Plav': -1.8, 'Pljevlja': -9.3,
        'Plužine': -12.8, 'Podgorica': 4.4, 'Rožaje': 5.5, 'Šavnik': -15.8, 'Tivat': 3.0, 'Tuzi': 4.0, 'Ulcinj': 1.0, 'Žabljak': -8.0, 'Zeta': 4.0}
out = {}
for m in MUNIS:
    a = [x.get(m) for x in h26]; b = [x.get(m) for x in h25]
    hn26 = sum(v[1] for v in a) if all(a) else None; hn25 = sum(v[1] for v in b) if all(b) else None
    out[m] = {'arrivals2025': t25.get(m, (None, None))[0], 'nights2025': t25.get(m, (None, None))[1],
              'hotel_nights_as2026': hn26, 'hotel_nights_as2025': hn25,
              'hotel_growth': round((hn26 / hn25 - 1) * 100, 1) if hn26 and hn25 else None,
              **({k: v for k, v in un.get(m, {}).items()}), 'nat_inc2025': NI25[m]}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('nights2025', sum(v['nights2025'] or 0 for v in out.values()), 'missing', [m for m in MUNIS if out[m]['nights2025'] is None])
print('unemp', sum(v.get('unemp', 0) for v in out.values()), 'missing', [m for m in MUNIS if 'unemp' not in out[m]])
print('hotel 26', sum(v['hotel_nights_as2026'] or 0 for v in out.values()), 'munis', sum(1 for v in out.values() if v['hotel_growth'] is not None))
print({m: out[m]['hotel_growth'] for m in MUNIS if out[m]['hotel_growth'] is not None})
