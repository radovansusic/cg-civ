# CG Civ - Crna Gora na heksovima

**Montenegro as a Civilization map.** 25 municipalities on 1,850 hexes, built only from real public data: MONSTAT, Census 2023, the employment agency, OpenStreetMap and Wikidata. Gold is the wage bill, Science is university graduates, Wonders are the most-documented landmarks.

**Mapa uživo / Live map: https://radovansusic.github.io/cg-civ/**

Interaktivna mapa Crne Gore u stilu Civilizacije. Svih 25 opština sa stvarnim podacima, preračunatim na mrežu od 1.850 heksova od po oko 8 km².

![CG Civ - mapa terena sa gradovima i čudima](docs/mapa.png)

| Pogled grada | Istraživač |
|---|---|
| ![Pogled grada Kotor](docs/pogled-grada.png) | ![Istraživač: fakultet i plata po opštinama](docs/istrazivac.png) |

Po uzoru na Karpathyjev [USA Civ](https://karpathy.ai/usaciv/). Napravio [Schule](https://schule.co.me), Podgorica · [schule.co.me](https://schule.co.me) · office@schule.co.me · X: [@SchuleDR](https://x.com/SchuleDR)

## Šta ima

- **Mapa:** teren izveden iz reljefa, gradovi (sjedišta opština), 20 čuda, elektrane.
- **24 sočiva:** 10 prinosa po heksu (zlato, proizvodnja, nauka, kultura, vjera, hrana, stanovnici, noćenja, reljef, teren) i 14 pokazatelja po opštini (plata, nezaposlenost, firme, rast firmi, fakultet, programiranje, turizam, vikendice, demografija, socijala, ljekari, gustina).
- **Pogled grada** za 25 opština: prinosi, distrikti po objavljenim pravilima, građani, popisi 1991-2011-2023, rang među opštinama.
- **9 savjetnika:** nalazi izračunati iz podataka, uz dugme koje pali odgovarajuće sočivo.
- **Istraživač:** bilo koja dva pokazatelja kao dijagram rasipanja sa korelacijom, plus tabela svih opština povezana sa mapom.

## Jezik Civilizacije

| Prinos | Šta znači u stvarnosti |
|---|---|
| Zlato | Masa neto zarada: zaposleni 2024 x neto plata 2025 x 12, u mil. €. Nije BDP, jer MONSTAT ne objavljuje BDP po opštinama. |
| Proizvodnja | Teren + aktivne firme 2025 (1 po 60) + elektrane (1 po 20 MW) |
| Nauka | Stanovnici sa fakultetom, Popis 2023 (1 po 300) |
| Kultura | Objekti baštine u OSM + noćenja 2024 (1 po 25.000) |
| Vjera | Broj bogomolja u OSM, bez podjele po vjeri |
| Hrana | Pravilo igre po terenu, +1 uz more i jezero |

Brojke opština raspoređene su po heksovima prema naseljenosti (Kontur). Noćenja su raspoređena prema smještajnim objektima (OSM). Zbir po opštini uvijek je jednak zvaničnom podatku.

## Izvori

- MONSTAT, Statistički godišnjak 2025, pogl. 28 (stanovništvo 1948-2023, demografija 2024, zaposleni 2024, turizam 2024, luke, škole, studenti, zdravstvo, MOP)
- MONSTAT, Popis 2023: pol i starost, obrazovna struktura (37/2025), rad na računaru (168/2024), stanovi (43/2025)
- MONSTAT, Mjesečni statistički pregled 10/2026, str. 29: prosječna neto zarada po opštinama, Ø 2025
- MONSTAT, Broj i struktura poslovnih subjekata u CG (2026): aktivni subjekti 2024 i 2025
- ZZZCG, bilten 1/2026: registrovani nezaposleni po opštinama, 31.1.2026.
- Kontur Boundaries i Kontur Population ME 2023 (CC BY 4.0)
- Terrarium visinske pločice (AWS Open Data / Mapzen)
- Natural Earth (javno dobro)
- © OpenStreetMap saradnici (ODbL): bogomolje, smještaj, baština
- Wikidata (CC0): elektrane i čuda

Kontrola zbirova: stanovnici 623.633, zaposleni 257.390, nezaposleni 26.833, firme 63.823, studenti 16.005, sa fakultetom 133.931. Sve je jednako zvaničnim ukupnim brojevima.

## Pokretanje

```bash
python3 -m http.server -d site 8000   # zatim otvori http://localhost:8000
# GitHub Pages: korijen repoa preusmjerava na site/; kopija je i u docs/
```

Ponovna izgradnja podataka (izvorni fajlovi idu u `raw/`, koji nije u repou):

```bash
pip install geopandas shapely pyogrio pdfplumber pillow pyproj
python3 scripts/fetch_wikidata.py     # Wikidata tačke
python3 scripts/extract_stats.py      # MONSTAT / ZZZCG PDF -> build/muni_stats.json
python3 scripts/build_hex.py          # heks mreža -> build/cgciv.json
cp build/cgciv.json site/
```

## Ograničenja

- Teren je izveden iz reljefa, nema sloja pokrivača tla (šume, njive).
- Gusinje, Petnjica i Tuzi nemaju objavljene podatke o turizmu.
- Zdravstveni radnici nijesu objavljeni za Gusinje, Petnjicu, Tuzi i Zetu.
- Plate po opštinama očitane su sa slike tabele u biltenu, pa ih treba provjeriti pri svakom ažuriranju.
