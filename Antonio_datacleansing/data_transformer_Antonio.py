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
- unidecode
- flake8 (Codequalität)
"""

import pandas as pd
from unidecode import unidecode

# ----------------------------
# 1. CSV-Datei einlesen
# ----------------------------

INPUT_PATH = "Antonio_datacleansing/scraping_output_Antonio.csv"
OUTPUT_PATH = "Antonio_datacleansing/clean_scraping_output_Antonio.csv"

df = pd.read_csv(INPUT_PATH)
print(f"Datei geladen: {len(df)} Zeilen, Spalten: {list(df.columns)}\n")

# ----------------------------
# 2. Texte bereinigen
# ----------------------------


def clean_text(text: str | None) -> str | None:
    """Korrigiert Kodierung, entfernt Leerzeichen und vereinheitlicht Text."""
    if isinstance(text, str):
        text = unidecode(text)  # ersetzt z. B. Ã¼ → ü
        text = text.replace("\n", " ").strip()
        return text
    return text


for col in ["titel", "land"]:
    df[col] = df[col].apply(clean_text)

print("Texte bereinigt.\n")

# ----------------------------
# 3. Preis & Versand trennen
# ----------------------------


def extract_price(value: str) -> tuple[str | None, float | None]:
    """Extrahiert Währung und numerischen Preis aus Strings wie 'CHF 33,52'."""
    if not isinstance(value, str):
        return None, None
    value = value.replace("'", "").replace(",", ".").strip()
    parts = value.split(" ")
    currency = None
    amount = None
    for p in parts:
        if p.replace(".", "", 1).isdigit():
            amount = float(p)
        elif len(p) == 3 and p.isalpha():
            currency = p.upper()
    return currency, amount


def extract_shipping(value: str) -> float:
    """Extrahiert Versandkosten in CHF oder 0 bei 'Kostenloser Versand'."""
    if not isinstance(value, str) or value.strip() == "":
        return 0.0
    if "Kostenlos" in value:
        return 0.0
    currency, amount = extract_price(value)
    return amount if amount else 0.0


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
    """Konvertiert Preis (inkl. Versand) in CHF."""
    rate = FX_RATES.get(row["waehrung"], 1.0)
    total = (row["preis_wert"] or 0) + (row["versand_wert"] or 0)
    return round(total / rate, 2)


df["preis_total_chf"] = df.apply(convert_to_chf, axis=1)
print("Preise einheitlich in CHF umgerechnet.\n")

# ----------------------------
# 5. Produktstatus vereinheitlichen
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
# 6. Doppelte Einträge entfernen
# ----------------------------

df.drop_duplicates(subset=["titel", "preis_total_chf", "link"], inplace=True)
print("Doppelte Einträge entfernt.\n")

# ----------------------------
# 7. Finale Struktur & Export
# ----------------------------

clean_df = df[
    ["titel", "zustand", "preis_total_chf", "land", "versand_wert", "link"]
].copy()

clean_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
print(f"Bereinigung abgeschlossen. Neue Datei gespeichert unter: {OUTPUT_PATH}\n")

if __name__ == "__main__":
    print("Normalize-Script erfolgreich ausgeführt – Daten sind bereit für Phase 3.")
