#!/usr/bin/env python3
"""
Prosty test ręcznej nawigacji do EU CTIS.
"""

import asyncio
from playwright.async_api import async_playwright

async def manual_ctis_test():
    """Test z możliwością ręcznej nawigacji."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Przeglądarka widoczna
            slow_mo=1000     # Wolne ruchy żeby lepiej widzieć
        )
        
        page = await browser.new_page()
        
        try:
            print("🌐 Otwieranie EU CTIS...")
            await page.goto("https://euclinicaltrials.eu/search-for-clinical-trials", 
                           wait_until="domcontentloaded", timeout=60000)
            
            print("✔ Strona załadowana")
            
            # Akceptuj cookies
            try:
                cookies_btn = page.locator("button:has-text('Accept all cookies')")
                if await cookies_btn.is_visible(timeout=5000):
                    await cookies_btn.click()
                    print("🍪 Cookies zaakceptowane")
                    await asyncio.sleep(3)
            except:
                print("⚠️  Brak cookie banner lub już zaakceptowane")
            
            # Poczekaj na załadowanie zawartości
            print("⏳ Czekanie na załadowanie zawartości...")
            try:
                # Czekaj na pojawienie się głównego formularza
                await page.wait_for_selector("form, .search-form, #search", timeout=15000)
                print("✔ Formularz wyszukiwania załadowany")
            except:
                print("⚠️  Timeout na formularz - sprawdzanie ręcznie")
            
            # Sprawdź obecny stan strony
            current_url = page.url
            title = await page.title()
            print(f"📍 URL: {current_url}")
            print(f"📄 Tytuł: {title}")
            
            # Sprawdź czy jest formularz wyszukiwania
            search_inputs = await page.locator("input[type='text'], input[type='search'], input[placeholder*='search']").count()
            print(f"🔍 Pola wyszukiwania: {search_inputs}")
            
            # Sprawdź przyciski
            visible_buttons = 0
            try:
                buttons = await page.locator("button:visible").all()
                for btn in buttons:
                    text = await btn.inner_text()
                    if text.strip() and len(text.strip()) < 50:  # Rozumne przyciski
                        print(f"   🔘 '{text.strip()}'")
                        visible_buttons += 1
                        if visible_buttons >= 10:  # Limit dla czytelności
                            break
            except:
                print("⚠️  Błąd przy odczytywaniu przycisków")
            
            print("\n" + "="*50)
            print("🧑‍💻 INSTRUKCJA MANUALNA:")
            print("1. Przeglądarka powinna być otwarta")
            print("2. Znajdź przycisk 'Advanced filters' lub podobny")
            print("3. Ustaw datę na wczoraj")
            print("4. Znajdź 'Download CSV' lub 'Export'")
            print("5. Naciśnij Ctrl+C w terminalu gdy skończysz")
            print("="*50)
            
            # Poczekaj na input użytkownika
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Zamykanie przeglądarki...")
                
        except Exception as e:
            print(f"❌ Błąd: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(manual_ctis_test())
