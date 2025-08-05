#!/usr/bin/env python3
# setup_local_db.py - Szybka konfiguracja lokalnej bazy

import psycopg
import os

def setup_local_sqlite():
    """Konfiguracja SQLite dla szybkiego startu"""
    print("🔧 Konfiguracja SQLite dla rozwoju...")
    
    # Instalacja SQLite adapter
    os.system(".venv\\Scripts\\pip install sqlite3")
    
    # Utworzenie lokalnej bazy SQLite
    import sqlite3
    
    conn = sqlite3.connect('trialwatch.db')
    cursor = conn.cursor()
    
    # Podstawowa tabela dla testów
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trials (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            source TEXT,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Test insert
    cursor.execute('''
        INSERT OR IGNORE INTO trials (id, title, status, source) 
        VALUES (?, ?, ?, ?)
    ''', ('NCT123456', 'Test Trial', 'RECRUITING', 'ClinicalTrials.gov'))
    
    conn.commit()
    
    # Test select
    cursor.execute('SELECT * FROM trials')
    results = cursor.fetchall()
    
    print(f"✅ SQLite baza utworzona: trialwatch.db")
    print(f"✅ Test danych: {len(results)} rekordów")
    
    conn.close()
    
    print(f"\n📝 Connection string dla SQLite:")
    print(f"sqlite:///./trialwatch.db")
    
    return "sqlite:///./trialwatch.db"

def test_postgresql_variants():
    """Test różnych wariantów PostgreSQL connection string"""
    
    # Możliwe hosty Railway
    possible_hosts = [
        "containers-us-west-201.railway.app",
        "postgres.railway.internal", 
        f"postgres-production-{hash('railway') % 10000}.up.railway.app",
        f"database.railway.app"
    ]
    
    password = "fjDBNaPGgXxUrQbfTFetxJgrKfjnzPGG"
    
    print("🔍 Testowanie możliwych Railway hostów...")
    
    for host in possible_hosts:
        for port in [5432, 7000, 6543]:
            conn_string = f"postgresql://postgres:{password}@{host}:{port}/railway"
            print(f"\n🧪 Test: {host}:{port}")
            
            try:
                with psycopg.connect(conn_string, connect_timeout=3) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT version();")
                        version = cur.fetchone()[0]
                        print(f"✅ SUKCES! {conn_string}")
                        print(f"Version: {version[:50]}...")
                        return conn_string
            except Exception as e:
                print(f"❌ {type(e).__name__}: {str(e)[:50]}...")
    
    return None

def main():
    print("🚀 Setup lokalnej bazy danych dla trialwatch")
    
    # Najpierw spróbuj Railway
    railway_conn = test_postgresql_variants()
    
    if railway_conn:
        print(f"\n🎉 Railway działa! Użyj:")
        print(f"{railway_conn}")
        
        # Zapisz do .env
        with open('.env', 'w') as f:
            f.write(f"DATABASE_URL={railway_conn}\n")
        print(f"💾 Zapisano do .env")
        
    else:
        print(f"\n⚠️ Railway niedostępne, używam SQLite...")
        sqlite_conn = setup_local_sqlite()
        
        # Zapisz do .env
        with open('.env', 'w') as f:
            f.write(f"DATABASE_URL={sqlite_conn}\n")
        print(f"💾 Zapisano do .env")

if __name__ == "__main__":
    main()
