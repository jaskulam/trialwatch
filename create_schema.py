#!/usr/bin/env python3
"""
Skrypt do tworzenia schematu bazy danych dla aplikacji trialwatch.
"""

import os
from db_client import PSQLWrapper

def create_schema():
    """Utworzenie schematu bazy danych dla badań klinicznych."""
    
    # SQL do utworzenia tabel
    create_tables_sql = """
    -- Tabela dla badań klinicznych z ClinicalTrials.gov
    CREATE TABLE IF NOT EXISTS clinical_trials (
        id SERIAL PRIMARY KEY,
        nct_id VARCHAR(20) UNIQUE NOT NULL,
        title TEXT NOT NULL,
        status VARCHAR(50),
        phase VARCHAR(50),
        start_date DATE,
        primary_completion_date DATE,
        completion_date DATE,
        study_type VARCHAR(100),
        sponsor TEXT,
        brief_summary TEXT,
        detailed_description TEXT,
        conditions TEXT[], -- Array dla wielu kondycji
        interventions TEXT[], -- Array dla wielu interwencji
        locations TEXT[], -- Array dla lokalizacji
        keywords TEXT[], -- Array dla słów kluczowych
        eligibility_criteria TEXT,
        gender VARCHAR(20),
        min_age VARCHAR(20),
        max_age VARCHAR(20),
        healthy_volunteers BOOLEAN,
        url TEXT,
        source VARCHAR(50) DEFAULT 'clinicaltrials.gov',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Tabela dla badań z EU CTIS (gdy będzie dostępne API)
    CREATE TABLE IF NOT EXISTS eu_clinical_trials (
        id SERIAL PRIMARY KEY,
        eu_ct_number VARCHAR(50) UNIQUE NOT NULL,
        title TEXT NOT NULL,
        status VARCHAR(50),
        phase VARCHAR(50),
        start_date DATE,
        end_date DATE,
        sponsor TEXT,
        brief_summary TEXT,
        therapeutic_area TEXT,
        population VARCHAR(100),
        countries TEXT[], -- Array krajów UE
        source VARCHAR(50) DEFAULT 'eu-ctis',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indeksy dla szybszego wyszukiwania
    CREATE INDEX IF NOT EXISTS idx_clinical_trials_nct_id ON clinical_trials(nct_id);
    CREATE INDEX IF NOT EXISTS idx_clinical_trials_status ON clinical_trials(status);
    CREATE INDEX IF NOT EXISTS idx_clinical_trials_phase ON clinical_trials(phase);
    CREATE INDEX IF NOT EXISTS idx_clinical_trials_conditions ON clinical_trials USING GIN(conditions);
    CREATE INDEX IF NOT EXISTS idx_clinical_trials_keywords ON clinical_trials USING GIN(keywords);
    CREATE INDEX IF NOT EXISTS idx_clinical_trials_last_updated ON clinical_trials(last_updated);

    CREATE INDEX IF NOT EXISTS idx_eu_clinical_trials_eu_ct_number ON eu_clinical_trials(eu_ct_number);
    CREATE INDEX IF NOT EXISTS idx_eu_clinical_trials_status ON eu_clinical_trials(status);
    CREATE INDEX IF NOT EXISTS idx_eu_clinical_trials_countries ON eu_clinical_trials USING GIN(countries);

    -- Tabela dla logów aktualizacji danych
    CREATE TABLE IF NOT EXISTS update_logs (
        id SERIAL PRIMARY KEY,
        source VARCHAR(50) NOT NULL,
        operation VARCHAR(50) NOT NULL,
        records_processed INTEGER DEFAULT 0,
        success BOOLEAN DEFAULT TRUE,
        error_message TEXT,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    try:
        client = PSQLWrapper()
        if not client.connect():
            print("❌ Nie można połączyć się z bazą danych")
            return False
            
        print("Tworzenie schematu bazy danych...")
        
        # Wykonaj SQL do tworzenia tabel
        result = client.execute_query(create_tables_sql)
        if result is not None:
            print("✅ Schemat bazy danych został utworzony pomyślnie!")
        else:
            print("❌ Błąd podczas tworzenia schematu")
            return False
        
        # Sprawdź utworzone tabele
        result = client.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        if result:
            print("\n📋 Utworzone tabele:")
            for row in result:
                print(f"  - {row[0]}")
            
        # Sprawdź strukturę głównej tabeli
        result = client.execute_query("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'clinical_trials' 
            ORDER BY ordinal_position;
        """)
        
        if result:
            print("\n🏗️ Struktura tabeli clinical_trials:")
            for row in result:
                nullable = "NULL" if row[2] == "YES" else "NOT NULL"
                print(f"  - {row[0]}: {row[1]} ({nullable})")
        
        client.close()
            
    except Exception as e:
        print(f"❌ Błąd podczas tworzenia schematu: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = create_schema()
    if success:
        print("\n🎉 Baza danych jest gotowa do użycia!")
    else:
        print("\n💥 Wystąpił problem podczas konfiguracji bazy danych.")
