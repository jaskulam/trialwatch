#!/usr/bin/env python3
"""
Test skryptu ctis_harvester.py bez AWS S3.
Pobiera CSV z EU CTIS i zapisuje lokalnie.
"""

import os, asyncio, time, pendulum
from pathlib import Path
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.async_api import async_playwright

load_dotenv()

DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "90"))
SEARCH_URL = "https://euclinicaltrials.eu/search-for-clinical-trials"

def today_path() -> Path:
    """Ścieżka do pliku CSV z dzisiejszą datą."""
    ts = pendulum.yesterday().format("YYYY-MM-DD")
    tmp = Path("./downloads") / f"ctis_{ts}.csv"
    tmp.parent.mkdir(exist_ok=True, parents=True)
    return tmp

@retry(wait=wait_exponential(multiplier=2, min=4, max=30),
       stop=stop_after_attempt(3))
async def test_harvest():
    """Test harvestingu bez uploadu do S3."""
    out_path = today_path()
    
    if out_path.exists():
        print(f"✔ CSV już istnieje: {out_path}")
        print(f"   Rozmiar: {out_path.stat().st_size/1e6:.1f} MB")
        return str(out_path)

    print(f"🌐 Otwieranie {SEARCH_URL}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False żeby zobaczyć
        ctx = await browser.new_context(accept_downloads=True)
        page = await ctx.new_page()

        try:
            await page.goto(SEARCH_URL, timeout=60000)
            print("✔ Strona załadowana")
            
            # Sprawdź czy strona się załadowała poprawnie
            title = await page.title()
            print(f"   Tytuł strony: {title}")
            
            # Zaakceptuj cookies jeśli są
            accept_cookies = page.locator("button:has-text('Accept all cookies')")
            if await accept_cookies.count() > 0:
                print("🍪 Akceptowanie cookies...")
                await accept_cookies.click()
                await asyncio.sleep(3)
            
            # Poczekaj na załadowanie strony po cookies
            await page.wait_for_load_state("networkidle")
            
            # Sprawdź czy przycisk Advanced filters istnieje
            advanced_btn = page.locator("button:has-text('Advanced filters')")
            if await advanced_btn.count() > 0:
                print("✔ Znaleziono przycisk 'Advanced filters'")
                await advanced_btn.click()
                await asyncio.sleep(2)
            else:
                print("⚠️  Nie znaleziono przycisku 'Advanced filters'")
                print("   Szukanie alternatywnych selektorów...")
                
                # Sprawdź inne możliwe selektory
                alt_selectors = [
                    "button[data-test='advanced-filters']",
                    "button[aria-label*='advanced']",
                    ".advanced-filters button",
                    "[data-cy*='advanced'] button"
                ]
                
                for selector in alt_selectors:
                    alt_btn = page.locator(selector)
                    if await alt_btn.count() > 0:
                        print(f"   ✔ Znaleziono alternatywny selektor: {selector}")
                        await alt_btn.click()
                        await asyncio.sleep(2)
                        break
                else:
                    print("   Dostępne przyciski na stronie:")
                    buttons = await page.locator("button").all()
                    for i, btn in enumerate(buttons[:10]):  # Pierwsze 10 przycisków
                        text = await btn.inner_text()
                        if text.strip():  # Tylko przyciski z tekstem
                            print(f"     {i}: '{text.strip()}'")
            
            # Sprawdź czy można ustawić datę
            date_selectors = [
                "input[placeholder='DD/MM/YYYY']",
                "input[type='date']",
                "input[placeholder*='date']",
                ".date-picker input"
            ]
            
            date_input = None
            for selector in date_selectors:
                test_input = page.locator(selector).first
                if await test_input.count() > 0:
                    date_input = test_input
                    print(f"✔ Znaleziono pole daty: {selector}")
                    break
            
            if date_input:
                yesterday = pendulum.yesterday().format("DD/MM/YYYY")
                print(f"✔ Ustawianie daty: {yesterday}")
                await date_input.fill(yesterday)
                await date_input.press("Enter")
                await asyncio.sleep(2)
            else:
                print("⚠️  Nie znaleziono pola daty")
                print("   Dostępne pola input:")
                inputs = await page.locator("input").all()
                for i, inp in enumerate(inputs[:5]):
                    placeholder = await inp.get_attribute("placeholder")
                    input_type = await inp.get_attribute("type")
                    print(f"     {i}: type='{input_type}' placeholder='{placeholder}'")
            
            # Sprawdź czy przycisk Download CSV istnieje
            download_selectors = [
                "button:has-text('Download CSV')",
                "button:has-text('Download')",
                "a:has-text('Download CSV')",
                "[data-test*='download'] button",
                ".download-csv",
                ".export-csv"
            ]
            
            download_btn = None
            for selector in download_selectors:
                test_btn = page.locator(selector)
                if await test_btn.count() > 0:
                    download_btn = test_btn.first
                    print(f"✔ Znaleziono przycisk download: {selector}")
                    break
            
            if download_btn:
                print("🔄 Próba pobrania CSV...")
                
                # Próba pobrania
                with page.expect_download(timeout=DOWNLOAD_TIMEOUT * 1000) as dl_info:
                    await download_btn.click()
                    print("⏳ Oczekiwanie na download...")
                
                download = await dl_info.value
                csv_path = await download.path()
                
                # Przenieś do naszego folderu
                Path(csv_path).rename(out_path)
                print(f"✔ Zapisano: {out_path}")
                print(f"   Rozmiar: {out_path.stat().st_size/1e6:.1f} MB")
                
            else:
                print("⚠️  Nie znaleziono przycisku download")
                print("   Wszystkie linki na stronie:")
                links = await page.locator("a").all()
                for i, link in enumerate(links[:10]):
                    text = await link.inner_text()
                    href = await link.get_attribute("href")
                    if "download" in (text + str(href)).lower():
                        print(f"     {i}: '{text}' -> {href}")
            
        except Exception as e:
            print(f"❌ Błąd: {e}")
            # Zrób screenshot dla debugowania
            screenshot_path = f"debug_screenshot_{pendulum.now().format('HH-mm-ss')}.png"
            await page.screenshot(path=screenshot_path)
            print(f"   Screenshot zapisany: {screenshot_path}")
            
        finally:
            await browser.close()

    return str(out_path) if out_path.exists() else None

if __name__ == "__main__":
    print("=== Test EU CTIS Harvester (bez AWS S3) ===")
    result = asyncio.run(test_harvest())
    if result:
        print(f"🎉 Sukces! Plik: {result}")
    else:
        print("💥 Nie udało się pobrać pliku")
