"""Extract municipal indicators from Monstat / ZZZCG PDFs into build/muni_stats.json.
Every field carries its source key; sources are listed in SOURCES."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pdfrows import page_rows, merge_numbers
import pdfplumber

RAW = os.path.join(os.path.dirname(__file__), '..', 'raw')
OUT = os.path.join(os.path.dirname(__file__), '..', 'build', 'muni_stats.json')

MUNIS = ['Andrijevica', 'Bar', 'Berane', 'Bijelo Polje', 'Budva', 'Cetinje', 'Danilovgrad', 'Gusinje',
         'Herceg Novi', 'Kolašin', 'Kotor', 'Mojkovac', 'Nikšić', 'Petnjica', 'Plav', 'Pljevlja', 'Plužine',
         'Podgorica', 'Rožaje', 'Šavnik', 'Tivat', 'Tuzi', 'Ulcinj', 'Žabljak', 'Zeta']

def norm(s):
    s = s.replace('Ко', 'Ko').replace('К', 'K').replace('о', 'o')
    tr = str.maketrans('šžčćđŠŽČĆĐ', 'szccdSZCCD')
    return s.translate(tr).lower().strip()

NORM = {norm(m): m for m in MUNIS}

def num(t):
    t = t.strip()
    if t in ('-', 'z', '…', '...'): return None
    t = t.replace(' ', '')
    if re.fullmatch(r'-?\d+,\d+', t): return float(t.replace(',', '.'))
    if re.fullmatch(r'-?\d+\.\d+', t): return float(t)
    if re.fullmatch(r'-?\d+', t): return int(t)
    return None

def rows(pdf, page, gap=3.5):
    """yield (muni or None, label_text, [values]) for each line"""
    for ws in page_rows(os.path.join(RAW, pdf), page):
        toks = merge_numbers(ws, gap)
        texts = [t['text'] for t in toks]
        # label = leading non-numeric tokens
        i = 0
        while i < len(texts) and num(texts[i]) is None and texts[i] not in ('-', 'z'):
            i += 1
        label = ' '.join(texts[:i])
        vals = [num(t) for t in texts[i:]]
        m = NORM.get(norm(label.split(' 1)')[0].replace('1)', '')))
        yield m, label, vals, texts

def simple_table(pdf, pages, gap=3.5):
    res = {}
    for p in pages:
        for m, label, vals, texts in rows(pdf, p, gap):
            if m and vals and m not in res:
                res[m] = vals
    return res

def year_table(pdf, pages, year):
    """tables where a municipality line starts with first year, following lines start with year"""
    res, cur = {}, None
    for p in pages:
        for m, label, vals, texts in rows(pdf, p):
            if m:
                cur = m
                if vals and vals[0] == year: res[m] = vals[1:]
            elif cur and vals and vals[0] == year and label == '':
                res.setdefault(cur, vals[1:])
            elif label and label.split()[0] in ('Zabljak',):
                pass
    return res

data = {m: {} for m in MUNIS}
def put(field, table, idx, src):
    for m in MUNIS:
        v = table.get(m)
        data[m][field] = v[idx] if v and len(v) > idx else None
    SRC[field] = src

SRC = {}
S_GOD = 'MONSTAT, Statistički godišnjak 2025, pogl. 28 Pregled po opštinama'
# population by censuses
t = simple_table('god28.pdf', [2])
for m in MUNIS:
    v = t[m]
    data[m]['pop2023'] = v[-1]
    data[m]['pop1991'] = v[5] if len(v) == 9 else None
    data[m]['pop2011'] = v[7] if len(v) == 9 else None
SRC['pop2023'] = 'MONSTAT, Popis 2023 (godišnjak 2025, tab. 28-1)'
SRC['pop1991'] = SRC['pop2011'] = 'MONSTAT, popisi (godišnjak 2025, tab. 28-1)'
t = simple_table('god28.pdf', [3]); put('households2023', {m: [v[-1]] for m, v in t.items()}, 0, 'MONSTAT, Popis 2023 (tab. 28-1)')
# demography 2024
t = year_table('god28.pdf', [6, 7], 2024)
put('natural_increase_rate', t, 1, S_GOD + ', tab. 28-3 (2024, na 1000)')
put('birth_rate', t, 2, S_GOD + ', tab. 28-3 (2024)')
put('death_rate', t, 3, S_GOD + ', tab. 28-3 (2024)')
# employment 2024
t = simple_table('god28.pdf', [10])
put('employed2024', t, 0, S_GOD + ', tab. 28-5 (godišnji prosjek 2024)')
# tourism 2024
t = year_table('god28.pdf', [25, 26], 2024)
put('tourists2024', t, 0, S_GOD + ', tab. 28-13 (2024, ukupan smještaj)')
put('tourists_foreign2024', t, 1, S_GOD + ', tab. 28-13')
put('nights2024', t, 2, S_GOD + ', tab. 28-13')
# schools
t = simple_table('god28.pdf', [28]); put('primary_pupils', t, 2, S_GOD + ', tab. 28-15 (2023/24)')
put('primary_schools', t, 0, S_GOD + ', tab. 28-15')
t = simple_table('god28.pdf', [29]); put('secondary_schools', t, 0, S_GOD + ', tab. 28-16 (2023/24)')
t = simple_table('god28.pdf', [30]); put('students2024', {m: [v[-1]] for m, v in t.items()}, 0, S_GOD + ', tab. 28-17 (studenti po prebivalištu 2024/25)')
t = simple_table('god28.pdf', [31]); put('health_workers', t, 0, S_GOD + ', tab. 28-18 (2023)')
put('physicians', t, 1, S_GOD + ', tab. 28-18 (2023)')
t = simple_table('god28.pdf', [36]); put('welfare_families', t, 0, S_GOD + ', tab. 28-21 (MOP 2024)')
put('welfare_members', t, 1, S_GOD + ', tab. 28-21 (MOP 2024)')
# census education (ENG release 37/2025, table 3)
t = simple_table('obraz.pdf', [3])
put('pop15plus', t, 0, 'MONSTAT, Popis 2023, Obrazovna struktura (saopštenje 37/2025)')
put('higher_ed', t, 6, 'MONSTAT, Popis 2023, Obrazovna struktura (saopštenje 37/2025)')
put('doctorates', t, 11, 'MONSTAT, Popis 2023, Obrazovna struktura (saopštenje 37/2025)')
# computer literacy
t = simple_table('racunar.pdf', [1])
put('programming_pct', t, 12, 'MONSTAT, Popis 2023, Poznavanje rada na računaru (saopštenje 168/2024)')
put('internet_pct', t, 10, 'MONSTAT, Popis 2023, Poznavanje rada na računaru (saopštenje 168/2024)')
# dwellings
t = simple_table('stanovi1.pdf', [3])
put('dwellings', t, 0, 'MONSTAT, Popis 2023, Stanovi (saopštenje 43/2025)')
put('dwellings_seasonal', t, 6, 'MONSTAT, Popis 2023, Stanovi (saopštenje 43/2025)')
put('dwellings_business', t, 4, 'MONSTAT, Popis 2023, Stanovi (saopštenje 43/2025)')
# age structure (census table 4)
age = {}
for p in range(2, 9):
    try:
        for m, label, vals, texts in rows('popis1.pdf', p):
            if m and len(vals) >= 17 and m not in age: age[m] = vals
    except IndexError:
        break
for m in MUNIS:
    v = age.get(m)
    if v:
        data[m]['age0_14'] = sum(v[1:4]); data[m]['age65plus'] = sum(v[14:17])
SRC['age0_14'] = SRC['age65plus'] = 'MONSTAT, Popis 2023, Stanovništvo prema polu i starosti (saopštenje 133/2024, tab. 4)'
# unemployed (ZZZCG bulletin Jan 2026, page 6 table)
t = {}
for line in pdfplumber.open(os.path.join(RAW, 'zzz_jan26.pdf')).pages[6].extract_text().split('\n'):
    mm = re.match(r'([^\d]+?) (\d+) (\d+) (\d+) ', line)
    if mm and norm(mm.group(1)) in NORM: t[NORM[norm(mm.group(1))]] = [int(mm.group(2))]
put('unemployed_jan2026', t, 0, 'Zavod za zapošljavanje CG, Mjesečni statistički bilten 1/2026 (stanje 31.1.2026)')
# net wages 2025 average - transcribed from MONSTAT Mjesečni statistički pregled 10/2026, str. 29 (image table)
WAGE = {'Andrijevica': 824, 'Bar': 942, 'Berane': 927, 'Bijelo Polje': 877, 'Budva': 1019, 'Cetinje': 964,
        'Danilovgrad': 898, 'Gusinje': 848, 'Herceg Novi': 961, 'Kolašin': 898, 'Kotor': 998, 'Mojkovac': 898,
        'Nikšić': 981, 'Petnjica': 824, 'Plav': 878, 'Pljevlja': 988, 'Plužine': 892, 'Podgorica': 1058,
        'Rožaje': 859, 'Šavnik': 882, 'Tivat': 1251, 'Tuzi': 881, 'Ulcinj': 863, 'Zeta': 1126, 'Žabljak': 947}
for m in MUNIS: data[m]['net_wage2025'] = WAGE[m]
SRC['net_wage2025'] = 'MONSTAT, Mjesečni statistički pregled 10/2026, str. 29 - prosječna neto zarada, Ø 2025'
# active business entities 2025 (MONSTAT, Broj i struktura poslovnih subjekata 2026, Tabela 1)
t = simple_table('firme.pdf', [1])
for m, a, b in [('Bijelo Polje', 1633, 1772), ('Plav', 150, 155), ('Rožaje', 810, 884)]:  # rows the x-gap parser splits; values read from same table text
    t.setdefault(m, [a, None, None, None, None, b])
put('firms2025', t, 5, 'MONSTAT, Broj i struktura poslovnih subjekata u CG (2026), tab. 1 - aktivni subjekti 2025')
put('firms2024', t, 0, 'MONSTAT, Broj i struktura poslovnih subjekata u CG (2026), tab. 1 - aktivni subjekti 2024')
# ports 2024 (tab. 28-14)
PORT = {'Bar': {'port_ships': 491, 'port_cargo_t': 2463054, 'port_pax': 36274},
        'Kotor': {'port_ships': 469, 'port_gt': 22591113}, 'Herceg Novi': {'port_ships': 16, 'port_cargo_t': 1438}}
for m, d in PORT.items(): data[m].update(d)
SRC['port_ships'] = S_GOD + ', tab. 28-14 (2024; Zelenika = Herceg Novi)'

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'munis': data, 'sources': SRC}, open(OUT, 'w'), ensure_ascii=False, indent=1)
# report gaps
for f in SRC:
    miss = [m for m in MUNIS if data[m].get(f) is None]
    if miss and f not in ('pop1991', 'pop2011', 'port_ships'): print('MISSING', f, miss)
print('ok', len(SRC), 'fields')
