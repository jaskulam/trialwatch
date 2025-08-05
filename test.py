# test.py
from ctgov import get_trials

print("Rozpoczynam wyszukiwanie badań klinicznych...")

# Szukamy badań dla "multiple myeloma" w fazie 2, rozpoczętych od 1 lipca 2025
trials_iterator = get_trials("multiple myeloma", phase="2", since="2025-07-01")

try:
    # Pobieramy pierwszy wynik z iteratora
    first_trial = next(trials_iterator)
    print("Znaleziono pierwsze badanie:")
    # Używamy .model_dump_json(indent=2) dla ładniejszego wydruku
    print(first_trial.model_dump_json(indent=2)) 
except StopIteration:
    print("Nie znaleziono żadnych badań spełniających kryteria.")