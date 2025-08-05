# ctgov.py – Wersja z ostateczną poprawką nazwy pola + integracja z PostgreSQL

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential

from db_client import PSQLWrapper

# ---- Konfiguracja z pliku .env (opcjonalnie) ----
load_dotenv()
CTG_ENDPOINT = os.getenv("CTG_ENDPOINT", "https://clinicaltrials.gov/api/v2/studies")
CTG_RPS = float(os.getenv("CTG_RPS", "5"))
PAGE_SIZE = int(os.getenv("CTG_PAGE_SIZE", "50"))
_SLEEP = 1.0 / CTG_RPS


# -----------------------------------------------------------------------------#
#                                MODELE DANYCH                                 #
# -----------------------------------------------------------------------------#
class IdentificationModule(BaseModel):
    nct_id: str = Field(alias="nctId")
    brief_title: Optional[str] = Field(alias="briefTitle", default=None)
    official_title: Optional[str] = Field(alias="officialTitle", default=None)

    @property
    def title(self) -> Optional[str]:
        return self.brief_title or self.official_title


class DesignModule(BaseModel):
    phases: List[str] = Field(default_factory=list)


class StatusModule(BaseModel):
    overall_status: str = Field(alias="overallStatus")
    last_changed_date: Optional[str] = Field(alias="lastChangedDate", default=None)


class ConditionsModule(BaseModel):
    conditions: List[str] = Field(default_factory=list)


class Location(BaseModel):
    country: Optional[str] = None


class ContactsLocationsModule(BaseModel):
    locations: List[Location] = Field(default_factory=list)


class ProtocolSection(BaseModel):
    identification_module: IdentificationModule = Field(alias="identificationModule")
    design_module: Optional[DesignModule] = Field(alias="designModule", default=None)
    status_module: StatusModule = Field(alias="statusModule")
    conditions_module: Optional[ConditionsModule] = Field(alias="conditionsModule", default=None)
    contacts_locations_module: Optional[ContactsLocationsModule] = Field(
        alias="contactsLocationsModule", default=None
    )


class ApiStudy(BaseModel):
    protocol_section: ProtocolSection = Field(alias="protocolSection")


class Trial(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: Optional[str] = None
    phases: List[str] = []
    status: str
    conditions: List[str] = []
    countries: List[str] = []
    last_changed: Optional[datetime] = None
    raw: Dict[str, Any] = {}

    @field_validator("last_changed", mode="before")
    @classmethod
    def _parse_dt(cls, v: Any) -> Optional[datetime]:
        """Bezpiecznie parsuje datę ze stringa do obiektu datetime."""
        if isinstance(v, str):
            v = v.replace("Z", "+00:00") if v.endswith("Z") else v
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return None
        return v

    @classmethod
    def from_api(cls, api: ApiStudy, raw: Dict[str, Any]) -> "Trial":
        """Tworzy instancję Trial z zagnieżdżonego obiektu odpowiedzi API."""
        p = api.protocol_section
        countries = []
        if p.contacts_locations_module:
            countries = [
                loc.country
                for loc in p.contacts_locations_module.locations
                if loc.country
            ]

        # Bezpiecznie obsłuż opcjonalne moduły
        phases = p.design_module.phases if p.design_module else []
        conditions = p.conditions_module.conditions if p.conditions_module else []

        return cls(
            id=p.identification_module.nct_id,
            title=p.identification_module.title,
            phases=phases,
            status=p.status_module.overall_status,
            conditions=conditions,
            countries=list(set(countries)),
            last_changed=p.status_module.last_changed_date,
            raw=raw,
        )


# -----------------------------------------------------------------------------#
#                             WYWOŁANIE API + RETRY                             #
# -----------------------------------------------------------------------------#
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
def _get(params: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.get(CTG_ENDPOINT, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print("HTTP", resp.status_code, resp.text[:200], "…")
        raise e
    return resp.json()


# -----------------------------------------------------------------------------#
#                                  PUBLIC API                                  #
# -----------------------------------------------------------------------------#
def get_trials(
    condition: str,
    phase: Optional[str] = None,
    since: Optional[str] = None,  # "YYYY-MM-DD"
    page_size: int = PAGE_SIZE,
) -> Iterator[Trial]:
    """
    Zwraca kolejne badania. Filtrowanie po fazie i dacie odbywa się lokalnie,
    aby zapewnić maksymalną stabilność i uniknąć błędów 400 Bad Request.
    """
    params = {
        "query.cond": condition,
        "pageSize": str(page_size),
        "fields": ",".join(
            [
                "NCTId", "BriefTitle", "OfficialTitle", "OverallStatus",
                "Phase", "Condition", "LastUpdatePostDate",
            ]
        ),
        "format": "json",
    }

    page_token: Optional[str] = None
    dt_since = datetime.fromisoformat(since) if since else None

    while True:
        if page_token:
            params["pageToken"] = page_token

        data = _get(params)
        for raw in data.get("studies", []):
            trial = Trial.from_api(ApiStudy.model_validate(raw), raw)

            if phase and phase not in [p.strip() for p in trial.phases]:
                continue
            if dt_since and trial.last_changed and trial.last_changed < dt_since:
                continue

            yield trial

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(_SLEEP)


def save_trials_to_db(trials: List[Trial], connection_string: str = None) -> int:
    """
    Zapisuje listę badań do bazy danych PostgreSQL z batch insert.
    Zwraca liczbę zapisanych rekordów.
    """
    if not trials:
        return 0
    
    client = PSQLWrapper(connection_string)
    if not client.connect():
        print("❌ Nie można połączyć z bazą danych")
        return 0
    
    try:
        # Przygotuj wszystkie wartości dla batch insert
        values_list = []
        for trial in trials:
            phases_str = ", ".join(trial.phases) if trial.phases else None
            conditions_array = trial.conditions if trial.conditions else []
            countries_array = trial.countries if trial.countries else []
            
            values = (
                trial.id,
                trial.title,
                trial.status,
                phases_str,
                conditions_array,
                countries_array,
                trial.last_changed or datetime.now(),
                'clinicaltrials.gov',
                f"https://clinicaltrials.gov/study/{trial.id}"
            )
            values_list.append(values)
        
        # Wykonaj batch insert
        with client.conn.cursor() as cur:
            # Dla psycopg3 - użyj executemany zamiast execute_values
            single_insert = """
                INSERT INTO clinical_trials (
                    nct_id, title, status, phase, conditions, locations,
                    last_updated, source, url
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (nct_id) 
                DO UPDATE SET
                    title = EXCLUDED.title,
                    status = EXCLUDED.status,
                    phase = EXCLUDED.phase,
                    conditions = EXCLUDED.conditions,
                    locations = EXCLUDED.locations,
                    last_updated = EXCLUDED.last_updated,
                    source = EXCLUDED.source,
                    url = EXCLUDED.url
            """
            
            cur.executemany(single_insert, values_list)
            client.conn.commit()
        
        print(f"✅ Zapisano {len(trials)} badań do bazy danych (batch)")
        return len(trials)
        
    except Exception as e:
        print(f"❌ Błąd podczas batch zapisu: {e}")
        client.conn.rollback()
        
        # Fallback - spróbuj po jednym
        print("   🔄 Próba zapisu pojedynczego...")
        saved_count = 0
        for trial in trials:
            try:
                phases_str = ", ".join(trial.phases) if trial.phases else None
                conditions_array = trial.conditions if trial.conditions else []
                countries_array = trial.countries if trial.countries else []
                
                single_insert = """
                    INSERT INTO clinical_trials (
                        nct_id, title, status, phase, conditions, locations,
                        last_updated, source, url
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (nct_id) DO NOTHING
                """
                
                params = (
                    trial.id, trial.title, trial.status, phases_str,
                    conditions_array, countries_array,
                    trial.last_changed or datetime.now(),
                    'clinicaltrials.gov',
                    f"https://clinicaltrials.gov/study/{trial.id}"
                )
                
                with client.conn.cursor() as cur:
                    cur.execute(single_insert, params)
                    client.conn.commit()
                    saved_count += 1
                    
            except Exception as single_error:
                print(f"   ❌ Błąd {trial.id}: {single_error}")
                client.conn.rollback()
                continue
        
        print(f"   💾 Fallback: zapisano {saved_count}/{len(trials)} badań")
        return saved_count
        
    finally:
        client.close()


def get_trials_and_save(
    condition: str,
    phase: Optional[str] = None,
    since: Optional[str] = None,
    page_size: int = PAGE_SIZE,
    max_trials: int = 100,
    batch_size: int = 10,
    connection_string: str = None
) -> int:
    """
    Pobiera badania z ClinicalTrials.gov i zapisuje je do bazy danych w batches.
    Zwraca liczbę zapisanych badań.
    """
    print(f"🔍 Wyszukiwanie badań dla: {condition}")
    if phase:
        print(f"   Faza: {phase}")
    if since:
        print(f"   Od daty: {since}")
    print(f"   Maksymalnie: {max_trials} badań, batch: {batch_size}")
    
    total_saved = 0
    batch = []
    count = 0
    
    try:
        for trial in get_trials(condition, phase, since, page_size):
            batch.append(trial)
            count += 1
            
            # Zapisz batch gdy osiągnie rozmiar lub gdy skończymy
            if len(batch) >= batch_size:
                saved = save_trials_to_db(batch, connection_string)
                total_saved += saved
                print(f"   📦 Batch {count//batch_size}: zapisano {saved}/{len(batch)} badań")
                batch = []  # Wyczyść batch
            
            if count >= max_trials:
                print(f"   🔚 Osiągnięto limit {max_trials} badań")
                break
                
            if count % 10 == 0:
                print(f"   📊 Pobrano {count} badań...")
        
        # Zapisz pozostały niepełny batch
        if batch:
            saved = save_trials_to_db(batch, connection_string)
            total_saved += saved
            print(f"   📦 Ostatni batch: zapisano {saved}/{len(batch)} badań")
        
        print(f"✅ Łącznie zapisano {total_saved}/{count} badań do bazy")
        return total_saved
        
    except Exception as e:
        print(f"❌ Błąd podczas pobierania/zapisu: {e}")
        # Spróbuj zapisać to co mamy w batch
        if batch:
            saved = save_trials_to_db(batch, connection_string)
            total_saved += saved
            print(f"   💾 Ratunkowy zapis: {saved}/{len(batch)} badań")
        return total_saved


def make_hash(trial: Trial) -> str:
    stamp = trial.last_changed.isoformat() if trial.last_changed else ""
    return hashlib.sha1(f"{trial.id}:{stamp}".encode()).hexdigest()


# -----------------------------------------------------------------------------#
#                                     TEST                                     #
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    print("=== Test ctgov.py z integracją PostgreSQL ===\n")
    
    # Test 1: Podstawowe pobranie badań
    print("1️⃣ Test podstawowego API:")
    try:
        count = 0
        for tr in get_trials("diabetes"):
            print(f"   {tr.id} | {tr.phases} | {tr.status} | {tr.title[:50]}...")
            count += 1
            if count >= 3:
                break
        print("   ✓ API działa poprawnie.\n")
    except Exception as exc:
        print(f"   ❌ Błąd API: {exc}\n")
    
    # Test 2: Zapis do bazy danych  
    print("2️⃣ Test zapisu do bazy danych:")
    try:
        saved = get_trials_and_save(
            condition="diabetes",  # Zmiana z cancer na diabetes (stabilniejsze API)
            max_trials=3,  # Tylko 3 badania dla szybkiego testu
            batch_size=2   # Małe batches
        )
        print(f"   ✅ Zapisano {saved} badań do PostgreSQL\n")
    except Exception as exc:
        print(f"   ❌ Błąd zapisu: {exc}\n")
    
    # Test 3: Sprawdzenie co jest w bazie
    print("3️⃣ Sprawdzenie danych w bazie:")
    try:
        client = PSQLWrapper()
        if client.connect():
            result = client.execute_query("""
                SELECT COUNT(*) as total, 
                       COUNT(DISTINCT status) as statuses,
                       MAX(last_updated) as last_update
                FROM clinical_trials;
            """)
            
            result2 = client.execute_query("""
                SELECT nct_id, title, status, phase 
                FROM clinical_trials 
                ORDER BY last_updated DESC 
                LIMIT 3;
            """)
            client.close()
            print("   ✅ Baza danych działa poprawnie")
        else:
            print("   ❌ Nie można połączyć z bazą")
    except Exception as exc:
        print(f"   ❌ Błąd bazy: {exc}")
    
    print("\n🎉 Wszystkie testy zakończone!")