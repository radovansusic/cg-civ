import asyncio, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        try: b = await p.chromium.launch()
        except Exception as e: print('launch fail', e); return
        pg = await b.new_page(viewport={'width': 1400, 'height': 860})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/cgciv/build/s1.png')
        await pg.click('button[data-t=advisors]'); await pg.wait_for_timeout(300)
        await pg.click('.lens[data-k="m:Neto plata 2025 €"]') if False else None
        await pg.evaluate("document.querySelector('.go').click()"); await pg.wait_for_timeout(500)
        await pg.screenshot(path='/home/claude/cgciv/build/s2.png')
        # open city: click on Podgorica banner area via evaluate
        await pg.evaluate("document.querySelector('button[data-t=explorer]').click()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path='/home/claude/cgciv/build/s3.png')
        await pg.evaluate("document.querySelector('#extab tbody tr').click()"); await pg.wait_for_timeout(300)
        # open city view directly
        await pg.mouse.wheel(0, 0)
        await pg.evaluate("window.dispatchEvent(new Event('x'))")
        print('errors', errs[:5])
        await pg.set_viewport_size({'width': 390, 'height': 800}); await pg.wait_for_timeout(600)
        await pg.screenshot(path='/home/claude/cgciv/build/s4.png', full_page=False)
        await b.close()
asyncio.run(main())
