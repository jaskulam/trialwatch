#!/usr/bin/env python3
# db_client.py - Wrapper dla psycopg z CLI podobnym do psql

import psycopg
import sys
from typing import Optional

class PSQLWrapper:
    def __init__(self, connection_string: str = None):
        if connection_string:
            self.conn_string = connection_string
        else:
            # Użyj connection string z .env
            self.conn_string = "postgresql://postgres:fjDBNaPGgXxUrQbfTFetxJgrKfjnzPGG@tramway.proxy.rlwy.net:31431/railway"
        self.conn: Optional[psycopg.Connection] = None
    
    def connect(self):
        """Połącz z bazą danych"""
        try:
            print("Próba połączenia z bazą danych...")
            self.conn = psycopg.connect(
                self.conn_string,
                connect_timeout=10,
                application_name="trialwatch_client"
            )
            print(f"✅ Połączono z bazą danych")
            return True
        except psycopg.OperationalError as e:
            print(f"❌ Błąd połączenia z bazą: {e}")
            print("💡 Sprawdź:")
            print("   - Czy serwer Railway jest dostępny")
            print("   - Czy connection string jest poprawny")
            print("   - Czy masz dostęp do internetu")
            return False
        except Exception as e:
            print(f"❌ Nieoczekiwany błąd: {e}")
            return False
    
    def execute_query(self, query: str):
        """Wykonaj zapytanie SQL"""
        if not self.conn:
            print("Brak połączenia z bazą")
            return None
        
        try:
            with self.conn.cursor() as cur:
                # Wykonaj zapytanie (może być wieloliniowe)
                cur.execute(query)
                
                # Sprawdź czy to zapytanie SELECT
                if cur.description:
                    results = cur.fetchall()
                    colnames = [desc[0] for desc in cur.description]
                    
                    if colnames and len(results) > 0:
                        print(" | ".join(colnames))
                        print("-" * (len(" | ".join(colnames))))
                    
                    for row in results:
                        print(" | ".join(str(cell) for cell in row))
                    
                    print(f"\n({len(results)} wierszy)")
                    return results
                else:
                    # Dla CREATE/INSERT/UPDATE/DELETE
                    self.conn.commit()
                    print(f"Zapytanie wykonane pomyślnie")
                    return True
                    
        except Exception as e:
            print(f"Błąd zapytania: {e}")
            if self.conn:
                self.conn.rollback()
            return None
    
    def interactive_mode(self):
        """Tryb interaktywny podobny do psql"""
        print("Mini-psql (wpisz 'quit' aby wyjść)")
        print("Przykładowe komendy:")
        print("  SELECT version();")
        print("  \\dt  (lista tabel)")
        print("  \\d table_name  (opis tabeli)")
        print()
        
        while True:
            try:
                query = input("trialwatch=> ").strip()
                
                if query.lower() in ['quit', 'exit', '\\q']:
                    break
                elif query == '\\dt':
                    self.execute_query("""
                        SELECT schemaname, tablename 
                        FROM pg_tables 
                        WHERE schemaname NOT IN ('information_schema', 'pg_catalog');
                    """)
                elif query.startswith('\\d '):
                    table_name = query[3:].strip()
                    self.execute_query(f"""
                        SELECT column_name, data_type, is_nullable 
                        FROM information_schema.columns 
                        WHERE table_name = '{table_name}';
                    """)
                elif query:
                    self.execute_query(query)
                    
            except KeyboardInterrupt:
                print("\nUżyj 'quit' aby wyjść")
            except EOFError:
                break
        
        print("Do widzenia!")
    
    def close(self):
        """Zamknij połączenie"""
        if self.conn:
            self.conn.close()
            print("Połączenie zamknięte")

def main():
    # Connection string z .env lub Railway
    conn_string = "postgresql://postgres:fjDBNaPGgXxUrQbfTFetxJgrKfjnzPGG@tramway.proxy.rlwy.net:31431/railway"
    
    client = PSQLWrapper(conn_string)
    
    if not client.connect():
        sys.exit(1)
    
    try:
        if len(sys.argv) > 1:
            # Wykonaj pojedyncze zapytanie
            query = " ".join(sys.argv[1:])
            client.execute_query(query)
        else:
            # Tryb interaktywny
            client.interactive_mode()
    finally:
        client.close()

if __name__ == "__main__":
    main()
