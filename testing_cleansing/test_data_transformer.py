# test_data_transformer.py
# Unit-Tests für Funktionen aus data_transformer_cleansing.py

from data_transformer_cleansing import (
    parse_number_eu,
    extract_currency,
    fix_grossbritannien,
)


def test_parse_number_eu_handles_german_format():
    """Testet, ob parse_number_eu deutsche Zahlformate korrekt umwandelt."""
    assert parse_number_eu("3.040,06") == 3040.06
    assert parse_number_eu("12,5") == 12.5
    assert parse_number_eu("10") == 10.0


def test_extract_currency_identifies_symbols():
    """Prüft, ob extract_currency verschiedene Währungen erkennt."""
    assert extract_currency("CHF 12.00") == "CHF"
    assert extract_currency("12,00 €") == "EUR"
    assert extract_currency("Usd 99") == "USD"
    assert extract_currency("£15") == "GBP"


def test_fix_grossbritannien_replaces_faulty_encoding():
    """Testet die Korrektur falsch encodierter 'Großbritannien'-Werte."""
    assert fix_grossbritannien("GroÃYbritannien") == "Grossbritannien"
    assert fix_grossbritannien("Großbritannien") == "Grossbritannien"
    assert fix_grossbritannien("Deutschland") == "Deutschland"
