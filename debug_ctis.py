#!/usr/bin/env python3
"""
Szczegółowy debug EU CTIS strony.
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_ctis_page():
    """Debugowanie struktury strony EU CTIS."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Nie headless żeby zobaczyć
        page = await browser.new_page()
        
        try:
            print("🌐 Nawigacja do EU CTIS...")
            await page.goto("https://euclinicaltrials.eu/search-for-clinical-trials", timeout=60000)
            
            print("🍪 Obsługa cookies...")
            accept_cookies = page.locator("button:has-text('Accept all cookies')")
            if await accept_cookies.count() > 0:
                await accept_cookies.click()
                print("   ✔ Cookies zaakceptowane")
                await asyncio.sleep(5)  # Dłuższe czekanie
            
            print("⏳ Czekanie na pełne załadowanie...")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            print("📄 Analiza struktury strony...")
            
            # Sprawdź URL po redirectach
            current_url = page.url
            print(f"   Aktualny URL: {current_url}")
            
            # Sprawdź tytuł
            title = await page.title()
            print(f"   Tytuł: {title}")
            
            # Sprawdź główne sekcje
            main_content = await page.locator("main, .main-content, #main").count()
            print(f"   Główna zawartość: {main_content} elementów")
            
            # Sprawdź formularze
            forms = await page.locator("form").count()
            print(f"   Formularze: {forms}")
            
            # Sprawdź wszystkie przyciski
            print("🔘 Wszystkie przyciski na stronie:")
            buttons = await page.locator("button").all()
            for i, btn in enumerate(buttons):
                text = await btn.inner_text()
                visible = await btn.is_visible()
                if visible and text.strip():
                    print(f"     {i}: '{text.strip()}'")
            
            # Sprawdź wszystkie pola input
            print("📝 Wszystkie pola input:")
            inputs = await page.locator("input").all()
            for i, inp in enumerate(inputs):
                visible = await inp.is_visible()
                if visible:
                    input_type = await inp.get_attribute("type")
                    placeholder = await inp.get_attribute("placeholder")
                    name = await inp.get_attribute("name")
                    print(f"     {i}: type='{input_type}' name='{name}' placeholder='{placeholder}'")
            
            # Sprawdź wszystkie linki z "download"
            print("🔗 Linki związane z download:")
            all_elements = await page.locator("*").all()
            download_elements = []
            for elem in all_elements:
                text = await elem.inner_text()
                if "download" in text.lower():
                    tag = await elem.evaluate("el => el.tagName")
                    print(f"     {tag}: '{text.strip()}'")
            
            # Sprawdź czy są jakieś loading spinnery
            loading = await page.locator(".loading, .spinner, [aria-label*='loading']").count()
            print(f"   Loading elements: {loading}")
            
            # Zrób screenshot
            await page.screenshot(path="ctis_debug.png")
            print("📸 Screenshot zapisany: ctis_debug.png")
            
            # Czekaj 10 sekund żeby użytkownik mógł zobaczyć stronę
            print("⏱️  Czekanie 10 sekund na manualną inspekcję...")
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"❌ Błąd: {e}")
            await page.screenshot(path="ctis_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_ctis_page())
