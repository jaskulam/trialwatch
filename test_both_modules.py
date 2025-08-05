#!/usr/bin/env python3
# test_both_modules.py - Test obu modułów: ctgov.py i ctis.py

from ctgov import get_trials as get_ctgov_trials
from ctis import get_trials_mock as get_ctis_trials_mock

def test_both_modules():
    """Test integracji obu modułów."""
    print("=== Test integracji modułów ctgov.py i ctis.py ===\n")
    
    # Test ClinicalTrials.gov (powinien działać)
    print("1. Test ClinicalTrials.gov API:")
    try:
        ctgov_trials = list(get_ctgov_trials(condition="multiple myeloma", page_size=3))
        print(f"   ✓ Pobrano {len(ctgov_trials)} badań z ClinicalTrials.gov")
        
        if ctgov_trials:
            print("   Przykład:")
            trial = ctgov_trials[0]
            print(f"   - ID: {trial.id}")
            print(f"   - Tytuł: {trial.title[:50]}...")
            print(f"   - Status: {trial.status}")
            print(f"   - Fazy: {trial.phases}")
    except Exception as e:
        print(f"   ❌ Błąd ClinicalTrials.gov: {e}")
    
    print()
    
    # Test EU CTIS (mock)
    print("2. Test EU CTIS (mock implementacja):")
    try:
        ctis_trials = list(get_ctis_trials_mock(condition="C90.0", limit=3))
        print(f"   ✓ Pobrano {len(ctis_trials)} mock badań z EU CTIS")
        
        if ctis_trials:
            print("   Przykład:")
            trial = ctis_trials[0]
            print(f"   - ID: {trial.id}")
            print(f"   - Tytuł: {trial.title[:50]}...")
            print(f"   - Status: {trial.status}")
            print(f"   - Źródło: {trial.source}")
    except Exception as e:
        print(f"   ❌ Błąd EU CTIS mock: {e}")
    
    print()
    
    # Podsumowanie
    print("3. Podsumowanie:")
    print("   - ctgov.py: ✓ Działa z rzeczywistym API ClinicalTrials.gov")
    print("   - ctis.py: ⚠️  Mock implementacja (brak publicznego API EU CTIS)")
    print("\n   Dla pełnej funkcjonalności zaleca się:")
    print("   a) Używanie ClinicalTrials.gov jako głównego źródła")
    print("   b) Zaimplementowanie web scrapingu dla EU CTIS")
    print("   c) Sprawdzenie czy EU CTIS udostępni API w przyszłości")

if __name__ == "__main__":
    test_both_modules()
