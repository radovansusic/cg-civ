"""Sveta mjesta u CG iz Wikidata (CC0): vjerski objekti i manastiri sa brojem Wikipedia jezika."""
import json, os, urllib.request, urllib.parse
RAW = os.path.join(os.path.dirname(__file__), '..', 'raw')
Q = """
SELECT ?item ?itemLabel ?coord ?sl (GROUP_CONCAT(DISTINCT ?tL; separator='|') AS ?types) (GROUP_CONCAT(DISTINCT ?rL; separator='|') AS ?rel) WHERE {
  { ?item wdt:P31/wdt:P279* wd:Q24398318. } UNION { ?item wdt:P31/wdt:P279* wd:Q44613. } UNION { VALUES ?item { wd:Q1192447 } }
  ?item wdt:P17 wd:Q236; wdt:P625 ?coord; wikibase:sitelinks ?sl.
  OPTIONAL { ?item wdt:P31 ?t. ?t rdfs:label ?tL. FILTER(lang(?tL)='en') }
  OPTIONAL { ?item wdt:P140 ?r. ?r rdfs:label ?rL. FILTER(lang(?rL)='en') }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "sh,sr-el,hr,bs,en". }
} GROUP BY ?item ?itemLabel ?coord ?sl ORDER BY DESC(?sl)"""
req = urllib.request.Request('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': Q, 'format': 'json'}), headers={'User-Agent': 'cg-civ/1.0 (schule.co.me)'})
rows = []
for b in json.load(urllib.request.urlopen(req, timeout=120))['results']['bindings']:
    lon, lat = map(float, b['coord']['value'].replace('Point(', '').replace(')', '').split())
    rows.append(dict(id=b['item']['value'].split('/')[-1], name=b['itemLabel']['value'], lon=lon, lat=lat, sitelinks=int(b['sl']['value']),
                     types=b.get('types', {}).get('value', ''), rel=b.get('rel', {}).get('value', '')))
json.dump(rows, open(os.path.join(RAW, 'wd_holy.json'), 'w'), ensure_ascii=False, indent=0)
print(len(rows))
for r in rows[:45]: print(r['sitelinks'], r['id'], r['name'], '|', r['types'][:50], '|', r['rel'])
