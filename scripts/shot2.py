import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); errs=[]
        pg = await b.new_page(viewport={'width': 1300, 'height': 820})
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(2500)
        # click on Budva city via computed coords
        xy = await pg.evaluate("""(()=>{const c=[...document.querySelectorAll('canvas')][0];return null})()""")
        await pg.mouse.click(1,1)
        await pg.evaluate("document.querySelector('button[data-t=explorer]').click()")
        await pg.wait_for_timeout(300)
        await pg.evaluate("[...document.querySelectorAll('#extab tbody tr')].find(t=>t.dataset.m==='Kotor').click()")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path='/home/claude/cgciv/build/s5.png')
        # find canvas center = Kotor city now centered; click there
        box = await pg.locator('#map').bounding_box()
        await pg.mouse.click(box['x']+box['width']/2, box['y']+box['height']/2)
        await pg.wait_for_timeout(500)
        await pg.screenshot(path='/home/claude/cgciv/build/s6.png')
        print('errors', errs)
        await b.close()
asyncio.run(main())
