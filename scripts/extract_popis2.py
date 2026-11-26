"""Census 2023 release II (MONSTAT 135/2024): nationality, religion, mother tongue, language spoken - shares by municipality."""
import pdfplumber, re, json, os
RAW = os.path.join(os.path.dirname(__file__), '..', 'raw')
OUT = os.path.join(os.path.dirname(__file__), '..', 'build', 'popis2.json')
PAIR = re.compile(r'(\d{1,3}(?: \d{3})*) (\d+,\d+)|([z-]) ([z-])')
data, titles, table, munis = {}, {}, None, []
for pg in pdfplumber.open(os.path.join(RAW, 'popis2.pdf')).pages:
    for line in (pg.extract_text() or '').split('\n'):
        m = re.match(r'Tabela (\d+)\. (.*?)(?:/nastavak/)?$', line.strip())
        if m:
            table = int(m.group(1)); titles.setdefault(table, m.group(2).strip()); continue
        if ' u %' in line and not re.search(r'\d', line):
            parts = [p.strip() for p in line.split(' u %') if p.strip()]
            if len(parts) >= 3: munis = parts
            continue
        if table is None or not munis: continue
        mm = re.match(r'([^\d]+?) (?=\d|z |- )(.*)$', line.strip())
        if not mm: continue
        label, rest = mm.group(1).strip(), mm.group(2)
        pairs = [(float(a[1].replace(',', '.')) if a[1] else None) for a in PAIR.findall(rest)]
        ms = munis
        if len(pairs) == len(munis) + 1: ms = ['CG'] + munis
        if len(pairs) != len(ms): continue
        for mu, v in zip(ms, pairs):
            data.setdefault(table, {}).setdefault(label, {})[mu.replace('Crna Gora', 'CG')] = v
# religion (table 2) is not transposed: rows are municipalities
rel = {}
pages = pdfplumber.open(os.path.join(RAW, 'popis2.pdf')).pages
for pi, cols in [(5, ['ukupno', 'pravoslavna', 'katolicka', 'protestantska', 'jehovini', 'ostale_hriscanske']),
                 (6, ['islamska', 'budisticka', 'ostale_vjere', 'ateisti', 'agnostici', 'ne_zeli', 'ostalo'])]:
    for line in pages[pi].extract_text().split('\n'):
        mm = re.match(r'([^\d]+?) (?=\d|z |- )(.*)$', line.strip())
        if not mm: continue
        pr = [(float(a[1].replace(',', '.')) if a[1] else None) for a in PAIR.findall(mm.group(2))]
        if len(pr) == len(cols):
            rel.setdefault(mm.group(1).strip().replace('Crna Gora', 'CG'), {}).update(dict(zip(cols, pr)))
data['religion'] = rel
json.dump({'titles': titles, 'data': data}, open(OUT, 'w'), ensure_ascii=False, indent=0)
for t in [1, 3, 4]:
    cats = list(data[t])
    print(t, titles[t][:90], '| cats', len(cats), cats[:12], '| munis', len(data[t][cats[0]]))
