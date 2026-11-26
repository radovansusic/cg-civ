"""Fetch Montenegro point features from Wikidata (CC0) into raw/wd_<cat>.json"""
import json, os, time, urllib.request, urllib.parse

RAW = os.path.join(os.path.dirname(__file__), '..', 'raw')
EP = 'https://query.wikidata.org/sparql'
LANG = 'sh,sr-el,hr,bs,en,sr'

def q(cls_clause, extra_vars='', extra=''):
    return f"""
SELECT DISTINCT ?item ?itemLabel ?coord {extra_vars} WHERE {{
  {cls_clause}
  ?item wdt:P17 wd:Q236; wdt:P625 ?coord.
  {extra}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{LANG}". }}
}}"""

QUERIES = {
    'settlements': q('?item wdt:P31/wdt:P279* wd:Q486972.', '?pop', 'OPTIONAL { ?item wdt:P1082 ?pop. }'),
    'national_parks': q('?item wdt:P31/wdt:P279* wd:Q46169.', '?area', 'OPTIONAL { ?item wdt:P2046 ?area. }'),
    'protected': q('?item wdt:P31/wdt:P279* wd:Q473972.'),
    'unesco': q('?item wdt:P1435 wd:Q9259.'),
    'unesco_parts': q('?item wdt:P1435 ?h. ?h wdt:P279* wd:Q9259.'),
    'power': q('?item wdt:P31/wdt:P279* wd:Q159719.', '?cap ?typeLabel', 'OPTIONAL { ?item wdt:P2109 ?cap. } OPTIONAL { ?item wdt:P31 ?type. }'),
    'dams': q('?item wdt:P31/wdt:P279* wd:Q12323.'),
    'airports': q('?item wdt:P31/wdt:P279* wd:Q1248784.'),
    'ports': q('?item wdt:P31/wdt:P279* wd:Q44782.'),
    'marinas': q('?item wdt:P31/wdt:P279* wd:Q721207.'),
    'universities': q('?item wdt:P31/wdt:P279* wd:Q3918.', '?students', 'OPTIONAL { ?item wdt:P2196 ?students. }'),
    'faculties': q('?item wdt:P31/wdt:P279* wd:Q180958.'),
    'monasteries': q('?item wdt:P31/wdt:P279* wd:Q44613.'),
    'churches': q('?item wdt:P31/wdt:P279* wd:Q16970.'),
    'mosques': q('?item wdt:P31/wdt:P279* wd:Q32815.'),
    'fortresses': q('?item wdt:P31/wdt:P279* wd:Q57821.'),
    'museums': q('?item wdt:P31/wdt:P279* wd:Q33506.'),
    'hospitals': q('?item wdt:P31/wdt:P279* wd:Q16917.'),
    'mines': q('?item wdt:P31/wdt:P279* wd:Q820477.'),
    'ski': q('?item wdt:P31/wdt:P279* wd:Q130003.'),
    'peaks': q('?item wdt:P31/wdt:P279* wd:Q8502.', '?elev', '?item wdt:P2044 ?elev. FILTER(?elev > 2000)'),
    'lakes': q('?item wdt:P31/wdt:P279* wd:Q23397.', '?area', 'OPTIONAL { ?item wdt:P2046 ?area. }'),
    'caves': q('?item wdt:P31/wdt:P279* wd:Q35509.'),
    'lighthouses': q('?item wdt:P31/wdt:P279* wd:Q39715.'),
    'stadiums': q('?item wdt:P31/wdt:P279* wd:Q483110.', '?cap', 'OPTIONAL { ?item wdt:P1083 ?cap. }'),
    'beaches': q('?item wdt:P31/wdt:P279* wd:Q40080.'),
    'islands': q('?item wdt:P31/wdt:P279* wd:Q23442.'),
    'bridges': q('?item wdt:P31/wdt:P279* wd:Q12280.'),
    'canyons': q('?item wdt:P31/wdt:P279* wd:Q150784.'),
    'rail_stations': q('?item wdt:P31/wdt:P279* wd:Q55488.'),
}

def run(name, sparql):
    url = EP + '?' + urllib.parse.urlencode({'query': sparql, 'format': 'json'})
    req = urllib.request.Request(url, headers={'User-Agent': 'cg-civ/0.1 (Schule research map)'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            rows = []
            for b in d['results']['bindings']:
                c = b['coord']['value']  # Point(lon lat)
                lon, lat = map(float, c[c.find('(') + 1:c.find(')')].split())
                row = {'id': b['item']['value'].rsplit('/', 1)[1], 'name': b.get('itemLabel', {}).get('value'), 'lon': lon, 'lat': lat}
                for k in ('pop', 'area', 'cap', 'students', 'elev', 'typeLabel'):
                    if k in b: row[k] = b[k]['value']
                rows.append(row)
            json.dump(rows, open(os.path.join(RAW, f'wd_{name}.json'), 'w'), ensure_ascii=False)
            return len(rows)
        except Exception as e:
            print(name, 'retry', e); time.sleep(5)
    return -1

if __name__ == '__main__':
    for n, s in QUERIES.items():
        print(n, run(n, s)); time.sleep(1)

FAMOUS = """
SELECT ?item ?itemLabel ?coord ?sl (GROUP_CONCAT(DISTINCT ?tL; separator='|') AS ?types) WHERE {
  ?item wdt:P17 wd:Q236; wdt:P625 ?coord; wikibase:sitelinks ?sl.
  FILTER(?sl >= 12)
  FILTER NOT EXISTS { ?item wdt:P31/wdt:P279* wd:Q486972. }
  FILTER NOT EXISTS { ?item wdt:P31/wdt:P279* wd:Q56061. }
  OPTIONAL { ?item wdt:P31 ?t. ?t rdfs:label ?tL. FILTER(LANG(?tL)='en') }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "sh,sr-el,hr,bs,en". }
} GROUP BY ?item ?itemLabel ?coord ?sl ORDER BY DESC(?sl) LIMIT 120
"""
def famous():
    url = EP + '?' + urllib.parse.urlencode({'query': FAMOUS, 'format': 'json'})
    req = urllib.request.Request(url, headers={'User-Agent': 'cg-civ/0.1 (Schule research map)'})
    d = json.load(urllib.request.urlopen(req, timeout=120))
    rows = []
    for b in d['results']['bindings']:
        c = b['coord']['value']; lon, lat = map(float, c[c.find('(') + 1:c.find(')')].split())
        rows.append({'id': b['item']['value'].rsplit('/', 1)[1], 'name': b['itemLabel']['value'], 'lon': lon, 'lat': lat,
                     'sitelinks': int(b['sl']['value']), 'types': b.get('types', {}).get('value', '')})
    json.dump(rows, open(os.path.join(RAW, 'wd_famous.json'), 'w'), ensure_ascii=False)
    return rows
