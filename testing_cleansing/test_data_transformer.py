# ---------------------------------------------------------------------
# Unit-Tests für Funktionen aus data_transformer_cleansing.py
# Testet Datenbereinigung: Zahlenformat, Währungserkennung, Encoding-Korrektur
# ---------------------------------------------------------------------

from data_transformer_cleansing import (
    parse_number_eu,
    extract_currency,
    fix_grossbritannien,
)

# ----------------------- Test 1 – Zahlenformate (Komma und Punkt im EU-Format) ----------------------- #


def test_parse_number_eu_handles_german_format():
    """Testet, ob parse_number_eu deutsche Zahlformate korrekt umwandelt."""
    # Erwartet: "3.040,06" → 3040.06 (Punkt als Tausendertrennzeichen, Komma als Dezimal)
    assert parse_number_eu("3.040,06") == 3040.06
    # Erwartet: "12,5" → 12.5 (einfaches Kommaformat)
    assert parse_number_eu("12,5") == 12.5
    # Erwartet: "10" → 10.0 (ganze Zahl als Float)
    assert parse_number_eu("10") == 10.0


# ----------------------- Test 2 – Währungserkennung (CHF, EUR, USD, GBP) ----------------------------- #


def test_extract_currency_identifies_symbols():
    """Prüft, ob extract_currency verschiedene Währungen erkennt."""
    # Schweizer Franken
    assert extract_currency("CHF 12.00") == "CHF"
    # Euro-Zeichen am Ende
    assert extract_currency("12,00 €") == "EUR"
    # US-Dollar in gemischter Schreibweise
    assert extract_currency("Usd 99") == "USD"
    # Britisches Pfund-Symbol
    assert extract_currency("£15") == "GBP"


# ----------------------- Test 3 – Encoding-Korrektur („Großbritannien“-Fehler) ----------------------- #


def test_fix_grossbritannien_replaces_faulty_encoding():
    """Testet die Korrektur falsch encodierter 'Großbritannien'-Werte."""
    # Falsch encodierter Text aus eBay-Daten: "GroÃYbritannien"
    assert fix_grossbritannien("GroÃYbritannien") == "Grossbritannien"
    # Richtige Schreibweise mit ß → ersetzt durch „ss“ für Konsistenz
    assert fix_grossbritannien("Großbritannien") == "Grossbritannien"
    # Kontrolle: andere Länder bleiben unverändert
    assert fix_grossbritannien("Deutschland") == "Deutschland"
