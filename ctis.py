# ctis.py - Wrapper dla publicznego API EU CTIS (ema.europa.eu)
# UWAGA: EU CTIS nie udostępnia publicznego REST API jak ClinicalTrials.gov
# Ten moduł pokazuje strukturę, która byłaby potrzebna gdyby API było dostępne

from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional

import requests
from pydantic import BaseModel, Field, ConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential

# --- Krok 1: Konfiguracja modułu ---
# UWAGA: Ten endpoint prawdopodobnie nie istnieje - EU CTIS nie udostępnia publicznego API
BASE_URL = "https://api.euclinicaltrials.eu/public/v1/trials"
RPS = 3  # Zgodnie z wytycznymi, 3 zapytania na sekundę
SLEEP_INTERVAL = 1.0 / RPS


# --- Krok 2: Definicja modeli danych ---

# Model docelowy, do którego będziemy mapować dane z obu źródeł
class UnifiedStudy(BaseModel):
    """Ujednolicony model reprezentujący badanie kliniczne z różnych źródeł."""
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    source: str  # np. "EU CTIS" lub "ClinicalTrials.gov"
    raw: Dict[str, Any]  # Zachowujemy oryginalne dane


# Model pomocniczy, mapujący odpowiedź z API CTIS
class CtisApiStudy(BaseModel):
    """Bezpośrednie mapowanie pól z 'entries' w odpowiedzi API CTIS."""
    trial_id: str = Field(alias="trialId")
    title: Optional[str] = Field(alias="title", default=None)
    trial_status: str = Field(alias="trialStatus")

    # Używamy ConfigDict do ignorowania dodatkowych pól z API
    model_config = ConfigDict(extra="ignore")


# --- Krok 3: Funkcja pomocnicza do pobierania danych ---
@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3))
def _fetch_page(params: Dict[str, Any]) -> Dict[str, Any]:
    """Pobiera jedną stronę wyników z API, z logiką ponowień."""
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# --- Funkcja pomocnicza do tworzenia mock danych ---
def _create_mock_trial_data() -> List[Dict[str, Any]]:
    """Tworzy przykładowe dane badań dla demonstracji struktury."""
    return [
        {
            "trialId": "EU-2023-001234",
            "title": "A Phase II Study of Novel Treatment for Multiple Myeloma",
            "trialStatus": "RECRUITING"
        },
        {
            "trialId": "EU-2023-005678", 
            "title": "Immunotherapy Approach in Multiple Myeloma Patients",
            "trialStatus": "ACTIVE"
        },
        {
            "trialId": "EU-2022-009876",
            "title": "Combination Therapy Study for Relapsed Multiple Myeloma", 
            "trialStatus": "COMPLETED"
        }
    ]


# --- Mock implementacja dla demonstracji ---
def get_trials_mock(condition: str, limit: int = 100) -> Iterator[UnifiedStudy]:
    """
    Mock implementacja pokazująca jak działałby moduł gdyby API było dostępne.
    """
    print(f"Mock: Symulacja pobierania danych dla condition='{condition}', limit={limit}")
    
    mock_data = _create_mock_trial_data()
    
    for i, entry in enumerate(mock_data):
        if i >= limit:
            break
            
        # Parsujemy i walidujemy dane
        api_study = CtisApiStudy.model_validate(entry)
        
        # Mapujemy na nasz ujednolicony model
        unified_study = UnifiedStudy(
            id=api_study.trial_id,
            title=api_study.title,
            status=api_study.trial_status,
            source="EU CTIS (MOCK)",
            raw=entry,
        )
        yield unified_study


# --- Alternatywna implementacja używająca EU Clinical Trials Register ---
def get_trials_from_eu_register(condition: str, limit: int = 100) -> Iterator[UnifiedStudy]:
    """
    Alternatywna funkcja używająca EU Clinical Trials Register.
    UWAGA: To również może nie mieć publicznego API.
    """
    print("Próba użycia EU Clinical Trials Register...")
    # EU Clinical Trials Register endpoint (również może nie istnieć)
    eu_register_url = "https://www.clinicaltrialsregister.eu/ctr-search/rest/studies"
    
    try:
        params = {
            "query": condition,
            "page": 1,
            "limit": min(limit, 100)
        }
        
        response = requests.get(eu_register_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Przykładowe parsowanie (struktura może być inna)
        for study in data.get("studies", []):
            yield UnifiedStudy(
                id=study.get("eudract_number", ""),
                title=study.get("title", ""),
                status=study.get("status", ""),
                source="EU Clinical Trials Register",
                raw=study
            )
            
    except Exception as e:
        print(f"EU Clinical Trials Register również niedostępny: {e}")
        print("Sugerowane rozwiązania:")
        print("1. Skorzystaj tylko z ClinicalTrials.gov API")
        print("2. Zaimplementuj web scraping dla EU CTIS")
        print("3. Użyj alternatywnych źródeł danych europejskich badań")
        return


# --- Główna funkcja z fallback ---
def get_trials(condition: str, limit: int = 100) -> Iterator[UnifiedStudy]:
    """
    Zwraca iterator badań klinicznych z EU CTIS dla podanego schorzenia.

    :param condition: Kod schorzenia (np. "C90.0" dla szpiczaka mnogiego).
    :param limit: Maksymalna liczba wyników do pobrania.
    :return: Iterator obiektów typu UnifiedStudy.
    """
    page_num = 1
    records_fetched = 0

    while records_fetched < limit:
        params = {
            "condition": condition,
            "page": page_num,
        }

        data = _fetch_page(params)
        entries = data.get("entries", [])

        # Jeśli strona nie zawiera żadnych wyników, to koniec paginacji
        if not entries:
            break

        for entry in entries:
            if records_fetched >= limit:
                break
            
            # Parsujemy i walidujemy dane z API
            api_study = CtisApiStudy.model_validate(entry)

            # Mapujemy na nasz ujednolicony model
            unified_study = UnifiedStudy(
                id=api_study.trial_id,
                title=api_study.title,
                status=api_study.trial_status,
                source="EU CTIS",
                raw=entry,
            )
            yield unified_study
            records_fetched += 1

        page_num += 1
        time.sleep(SLEEP_INTERVAL)


# --- Krok 5: Test działania modułu ---
if __name__ == "__main__":
    print("--- Test modułu ctis.py ---")
    print("UWAGA: EU CTIS nie udostępnia publicznego REST API jak ClinicalTrials.gov")
    print("Demonstracja z użyciem mock danych...")

    try:
        # Test z mock danymi
        trials_to_fetch = 3
        print(f"\nTest mock implementacji (limit: {trials_to_fetch}):")
        mock_trials = list(get_trials_mock(condition="C90.0", limit=trials_to_fetch))
        
        print(f"Pobrano {len(mock_trials)} mock badań:")
        for trial in mock_trials:
            print(
                f"  ID: {trial.id} | Status: {trial.status} | Source: {trial.source}"
            )
            print(f"  Tytuł: {trial.title}")
            print()
        
        print("✓ Mock implementacja działa poprawnie.")
        print("\nGdyby EU CTIS udostępniło API, można by zastąpić funkcję get_trials_mock() funkcją get_trials()")
        
        # Próba rzeczywistego API (prawdopodobnie nie powiedzie się)
        print(f"\nPróba rzeczywistego API (prawdopodobnie nie powiedzie się):")
        real_trials = list(get_trials(condition="C90.0", limit=1))
        
        if real_trials:
            print("✓ Rzeczywiste API działa!")
        else:
            print("Brak danych z rzeczywistego API")

    except Exception as e:
        print(f"\nRzeczywiste API nie działa (oczekiwane): {type(e).__name__}")
        print("\nALTERNATYWNE ROZWIĄZANIA:")
        print("1. Użyj EU Clinical Trials Register: https://www.clinicaltrialsregister.eu/")
        print("2. Sprawdź dokumentację EU CTIS pod kątem dostępności API")
        print("3. Rozważ web scraping strony wyszukiwania CTIS")
        print("4. Użyj tylko ClinicalTrials.gov API dla uzyskania danych o badaniach")