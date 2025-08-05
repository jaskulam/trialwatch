#!/usr/bin/env python3
# test_connection.py - Test różnych konfiguracji połączenia

import psycopg
import sys

def test_connection(conn_string: str, description: str):
    """Test połączenia z bazą danych"""
    print(f"\n🔍 Test: {description}")
    print(f"Connection string: {conn_string}")
    
    try:
        with psycopg.connect(conn_string, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"✅ Połączono! Version: {version[:50]}...")
                return True
    except psycopg.OperationalError as e:
        print(f"❌ Błąd operacyjny: {e}")
        return False
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return False

def main():
    # Nowy ZEWNĘTRZNY connection string z Railway
    external_conn_string = "postgresql://postgres:fjDBNaPGgXxUrQbfTFetxJgrKfjnzPGG@tramway.proxy.rlwy.net:31431/railway"
    
    print("🚀 Testowanie ZEWNĘTRZNEGO Railway connection string")
    
    if test_connection(external_conn_string, "Railway External Connection"):
        print(f"\n🎉 SUKCES! Connection string działa:")
        print(f"{external_conn_string}")
        
        # Zapisz do .env
        try:
            with open('.env', 'w') as f:
                f.write(f"DATABASE_URL={external_conn_string}\n")
            print(f"💾 Zapisano do .env")
        except Exception as e:
            print(f"⚠️ Nie można zapisać .env: {e}")
        
        return
    
    # Fallback - stary sposób testowania
    host = "containers-us-west-201.railway.app"
    user = "postgres"
    password = "s3cr3t"
    db = "railway"
    
    # Typowe porty PostgreSQL
    ports_to_try = [7000, 5432, 6543, 5433, 25432]
    
    print("\n� Testowanie starych konfiguracji...")
    
    for port in ports_to_try:
        conn_string = f"postgres://{user}:{password}@{host}:{port}/{db}"
        if test_connection(conn_string, f"Port {port}"):
            print(f"\n🎉 SUKCES! Użyj tego connection string:")
            print(f"postgres://{user}:{password}@{host}:{port}/{db}")
            return
    
    print(f"\n💡 MOŻLIWE PRZYCZYNY:")
    print(f"1. postgres.railway.internal dostępny tylko z Railway")
    print(f"2. Potrzebujesz zewnętrznego connection string")
    print(f"3. Baza danych Railway jest nieaktywna/zatrzymana")
    print(f"4. Connection string jest niepoprawny")
    
    print(f"\n🔧 SPRAWDŹ W RAILWAY DASHBOARD:")
    print(f"- Variables -> DATABASE_URL")
    print(f"- Connect -> External connection")
    print(f"- Czy baza jest uruchomiona")

if __name__ == "__main__":
    main()
