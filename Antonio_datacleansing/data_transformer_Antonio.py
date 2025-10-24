"""
Data Cleansing und Normalisierung (PriceHunter)
---------------------------------------------------------
Funktion:
1. CSV-Datei aus "Scraping.py" laden (scraping_output_Antonio.csv)
2. Texte bereinigen (Umlaute, Leerzeichen, fehlerhafte Kodierungen)
3. Preis & Versand trennen und in CHF konvertieren
4. Produktstatus vereinheitlichen (Brandneu, Gebraucht, etc.)
5. Doppelte Inserate entfernen
6. Einheitliche Struktur exportieren als clean_guitars_Antonio.csv

Abhängigkeiten:
- pandas
- ftfy
- flake8 (Codequalität)
"""

import pandas as pd
import re
from ftfy import fix_text

# ----------------------------
# 1. CSV-Datei einlesen
# ----------------------------

INPUT_PATH = "Antonio_datacleansing/scraping_output_Antonio.csv"
OUTPUT_PATH = "Antonio_datacleansing/clean_scraping_output_Antonio.csv"

df = pd.read_csv(INPUT_PATH, encoding_errors="replace")

from ftfy import fix_encoding

for col in ["titel", "land"]:
    df[col] = df[col].apply(lambda x: fix_encoding(x) if isinstance(x, str) else x)

# ----------------------------
# 2. Texte bereinigen
# ----------------------------


def clean_text(text: str | None) -> str | None:
    """
    Korrigiert fehlerhafte Kodierungen (z. B. 'ZÃ¼rich' → 'Zürich'),
    behält aber Umlaute wie ä, ö, ü bei.
    """
    if not isinstance(text, str):
        return text

    text = text.strip().replace("\n", " ")

    # Immer ftfy verwenden, da es Umlaute repariert und beibehält
    text = fix_text(text)
    return text


for col in ["titel", "land"]:
    df[col] = df[col].apply(clean_text)

print("Texte bereinigt (intelligente Kodierungsprüfung aktiv).\n")

# ----------------------------
# 3. Preis & Versand trennen
# ----------------------------


def extract_price(value: str) -> tuple[str | None, float]:
    """Extrahiert Währung und numerischen Preis aus Strings wie 'CHF 33,52'.
    Gibt 0.00 zurück, wenn kein Preis erkannt wird (immer mit zwei Dezimalstellen).
    """
    if not isinstance(value, str) or value.strip() == "":
        return None, 0.00

    value = value.replace("'", "").replace(",", ".").strip()
    parts = value.split(" ")
    currency = None
    amount = 0.00  # Standardwert

    for p in parts:
        if p.replace(".", "", 1).isdigit():
            amount = round(float(p), 2)  # hier wird auf zwei Nachkommastellen gerundet
        elif len(p) == 3 and p.isalpha():
            currency = p.upper()

    return currency, amount


def extract_shipping(value: str) -> float:
    """Extrahiert Versandkosten in CHF oder 0.00 bei 'Kostenloser Versand'.
    Gibt immer eine Zahl mit zwei Dezimalstellen zurück.
    """
    if not isinstance(value, str) or value.strip() == "":
        return 0.00
    if "Kostenlos" in value:
        return 0.00
    currency, amount = extract_price(value)
    return round(amount, 2) if amount else 0.00


df[["waehrung", "preis_wert"]] = df["preis"].apply(
    lambda x: pd.Series(extract_price(x))
)
df["versand_wert"] = df["versand"].apply(extract_shipping)

print("Preis- und Versandfelder extrahiert.\n")

# ----------------------------
# 4. Preise in CHF konvertieren
# ----------------------------

FX_RATES = {"EUR": 0.95, "USD": 0.88, "GBP": 0.77, "CHF": 1.0}


def convert_to_chf(row) -> float:
    """Konvertiert Preis (inkl. Versand) in CHF.
    Gibt 0.00 zurück, wenn kein Produktpreis vorhanden ist.
    """
    rate = FX_RATES.get(row["waehrung"], 1.0)

    # Kein Produktpreis → kein Gesamtpreis
    if not isinstance(row["preis_wert"], (int, float)) or row["preis_wert"] == 0.0:
        return 0.00

    # Versandkosten sicherstellen
    versand = (
        row["versand_wert"] if isinstance(row["versand_wert"], (int, float)) else 0.0
    )

    total = row["preis_wert"] + versand
    return round(total / rate, 2)


# Neue Spalte mit Gesamtpreis in CHF
df["preis_total_chf"] = df.apply(convert_to_chf, axis=1)

print("Preise erfolgreich in CHF umgerechnet.\n")

df["preis_total_chf"] = df["preis_total_chf"].round(2)
df["preis_wert"] = df["preis_wert"].round(2)
df["versand_wert"] = df["versand_wert"].round(2)

# ----------------------------
# 5. Länderbezeichnungen bereinigen
# ----------------------------

# Mapping-Tabelle: unklare oder gemischte Herkunftsangaben → einheitliche Ländernamen
country_map = {
    "aus Deutschland": "Deutschland",
    "aus Schweiz": "Schweiz",
    "aus Grossbritannien": "Grossbritannien",
    "aus Frankreich": "Frankreich",
    "aus Spanien": "Spanien",
    "aus Italien": "Italien",
}


def clean_country(value: str) -> str:
    """Bereinigt Länderangaben, entfernt 'aus' und vereinheitlicht Namen."""
    if not isinstance(value, str) or value.strip() == "":
        return "Unbekannt"
    value = value.strip()
    # Mapping zuerst prüfen
    if value in country_map:
        return country_map[value]
    # Wenn kein Mapping vorhanden, nur 'aus' entfernen
    return value.replace("aus ", "").strip()


# Neue Spalte 'land' bereinigen
df["land"] = df["land"].apply(clean_country)

print("Länderbezeichnungen bereinigt.\n")

# ----------------------------
# 6. Produktstatus vereinheitlichen
# ----------------------------


def normalize_condition(text: str) -> str:
    """Extrahiert und vereinheitlicht Zustandsangabe (neu/gebraucht)."""
    if not isinstance(text, str):
        return "unbekannt"
    text = text.lower()
    if "neu" in text or "brandneu" in text:
        return "neu"
    if "gebraucht" in text:
        return "gebraucht"
    if "ersatzteil" in text:
        return "defekt"
    return "unbekannt"


df["zustand"] = df["aktualitaet"].apply(normalize_condition)

# ----------------------------
# 7. Doppelte Einträge entfernen
# ----------------------------

df.drop_duplicates(subset=["titel", "preis_total_chf", "link"], inplace=True)
print("Doppelte Einträge entfernt.\n")

# ----------------------------
# 8. Finale Struktur & Export
# ----------------------------

clean_df = df[
    ["titel", "zustand", "preis_total_chf", "land", "versand_wert", "link"]
].copy()

# Export mit zwei Dezimalstellen bei Float-Werten
clean_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8", float_format="%.2f")
print(f"Bereinigung abgeschlossen. Neue Datei gespeichert unter: {OUTPUT_PATH}\n")

if __name__ == "__main__":
    print(
        "Normalize-Script erfolgreich ausgeführt – Daten sind bereit für Feature-Frontend."
    )
