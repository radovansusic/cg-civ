import asyncio, os, subprocess
from playwright.async_api import async_playwright
V = '/home/claude/cgciv/video'; URL = 'http://localhost:8765/index.html'
CAP = """(t)=>{let d=document.getElementById('cap');if(!d){d=document.createElement('div');d.id='cap';d.style.cssText='position:fixed;left:0;right:0;bottom:28px;text-align:center;z-index:50;pointer-events:none';document.body.appendChild(d)}
d.innerHTML=t?`<span style="background:rgba(99,13,61,.92);color:#fff;font:700 30px Caladea,serif;padding:10px 22px;border-radius:10px">${t}</span>`:''}"""
CARD = """(o)=>{let d=document.getElementById('card');if(!d){d=document.createElement('div');d.id='card';document.body.appendChild(d)}
d.style.cssText='position:fixed;inset:0;z-index:60;background:#630D3D;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-family:Caladea,serif';
d.innerHTML=o?`<div style="font-size:64px;font-weight:700">${o[0]}</div><div style="font:28px Carlito,sans-serif;margin-top:14px;opacity:.9">${o[1]}</div><div style="font:22px Carlito,sans-serif;margin-top:28px;color:#d9a441">${o[2]}</div>`:'';if(!o)d.remove()}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1280, 'height': 720})
        await pg.goto(URL); await pg.wait_for_timeout(2500)
        await pg.add_style_tag(content='#tip{display:none!important}')
        async def still(name, cap=None):
            await pg.evaluate(CAP, cap or ''); await pg.wait_for_timeout(250)
            await pg.screenshot(path=f'{V}/{name}.jpg', type='jpeg', quality=92)
        await pg.evaluate(CARD, ['CG Civ', 'Montenegro as a Civilization map', '25 municipalities · 1,850 hexes · real public data'])
        await pg.wait_for_timeout(400); await pg.screenshot(path=f'{V}/00_title.jpg', type='jpeg', quality=92)
        await pg.evaluate(CARD, None)
        # zoom sequence on terrain toward the coast (Boka)
        await pg.evaluate(CAP, 'Terrain from real elevation, cities, wonders, power plants')
        os.makedirs(f'{V}/zoom', exist_ok=True)
        box = await pg.locator('#map').bounding_box()
        cx, cy = box['x'] + box['width'] * 0.34, box['y'] + box['height'] * 0.68
        for i in range(90):
            await pg.mouse.move(cx, cy); await pg.mouse.wheel(0, -14)
            await pg.wait_for_timeout(15)
            await pg.screenshot(path=f'{V}/zoom/{i:03d}.jpg', type='jpeg', quality=92)
        await pg.click('#zfit'); await pg.wait_for_timeout(300)
        for i, (lens, cap) in enumerate([('gold', 'Gold = annual net wage bill (MONSTAT)'), ('m:Indeks bogatstva', 'Wealth index: wages, firms, second homes, graduates'),
                                         ('cat:_nacija', 'Largest nation per municipality, Census 2023'), ('nights', 'Tourism: 15.6 million overnight stays'),
                                         ('m:Fakultet % (15+)', 'Science: share with a university degree')]):
            await pg.evaluate(f"document.querySelector('.lens[data-k=\"{lens}\"]').click()")
            await still(f'1{i}_lens', cap)
        await pg.evaluate(CAP, '')
        await pg.evaluate("document.querySelector('button[data-t=explorer]').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("[...document.querySelectorAll('#extab tbody tr')].find(t=>t.dataset.m==='Kotor').click()"); await pg.wait_for_timeout(300)
        box = await pg.locator('#map').bounding_box()
        await pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2); await pg.wait_for_timeout(500)
        await still('20_city', 'City view for all 25 municipalities')
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)
        await still('30_explorer', 'Explorer: any two indicators, linked to the map')
        await pg.evaluate(CAP, '')
        await pg.evaluate(CARD, ['radovansusic.github.io/cg-civ', 'Open source on GitHub · data: MONSTAT, Census 2023, OSM, Wikidata', 'Schule · schule.co.me'])
        await pg.wait_for_timeout(400); await pg.screenshot(path=f'{V}/90_end.jpg', type='jpeg', quality=92)
        await b.close()
asyncio.run(main())
