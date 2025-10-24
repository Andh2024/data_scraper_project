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
import requests
import json
from datetime import datetime, timedelta
import os
import argparse

os.makedirs("Antonio_datacleansing", exist_ok=True)

# ----------------------------
# 1. CLI-Argumente & CSV-Datei einlesen
# ----------------------------

# Argumentparser konfigurieren
parser = argparse.ArgumentParser(
    description="Bereinigt Scraping-Daten (Texte, Preise, Währungen, Länder, Duplikate)."
)
parser.add_argument(
    "--input",
    type=str,
    default="Antonio_datacleansing/scraping_output_Antonio.csv",
    help="Pfad zur Eingabedatei (CSV aus Scraping-Phase).",
)
parser.add_argument(
    "--output",
    type=str,
    default="Antonio_datacleansing/clean_scraping_output_Antonio.csv",
    help="Pfad zur Ausgabedatei (bereinigte CSV).",
)

args = parser.parse_args()

INPUT_PATH = args.input
OUTPUT_PATH = args.output

# Sicherstellen, dass Zielverzeichnis existiert
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

df = pd.read_csv(INPUT_PATH)
print(f"Datei geladen: {len(df)} Zeilen, Spalten: {list(df.columns)}\n")

print(f"Input-Datei: {INPUT_PATH}")
print(f"Output-Datei: {OUTPUT_PATH}\n")

# ----------------------------
# 1a. Schema-Validierung (Pflichtspalten prüfen)
# ----------------------------
REQUIRED_COLUMNS = ["titel", "aktualitaet", "preis", "land", "versand", "link"]
missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]

if missing_cols:
    print(f"⚠️ Fehlende Pflichtspalten im Eingabefile: {missing_cols}")
    print("Bitte Scraping-Datei überprüfen – Bereinigung wird abgebrochen.")
    exit(1)  # Skript sicher beenden
else:
    print("Schema-Check erfolgreich: Alle Pflichtspalten vorhanden.\n")

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
# 3. Preis & Währung trennen (vektorisiert)
# ----------------------------
import re

# 1) Währungs-Mapping
currency_map = {
    "CHF": "CHF",
    "FR": "CHF",
    "FR.": "CHF",
    "SFR": "CHF",
    "SFR.": "CHF",
    "EUR": "EUR",
    "€": "EUR",
    "USD": "USD",
    "$": "USD",
    "GBP": "GBP",
    "£": "GBP",
}

# 2) Regex zum Erkennen von Beträgen & Währungen
price_re = re.compile(
    r"(?i)\s*(?P<cur1>CHF|S?FR\.?|EUR|€|USD|\$|GBP|£)?\s*"
    r"(?P<amt>[\d\.\,'’\s]+(?:[.,]\d{1,2})?|\d+\.-)"
    r"\s*(?P<cur2>CHF|S?FR\.?|EUR|€|USD|\$|GBP|£)?\s*"
)

# 3) Ganze Spalte "preis" parsen
m = df["preis"].astype(str).str.extract(price_re)

# 4) Währung zusammenführen & vereinheitlichen
df["waehrung"] = (
    m["cur1"]
    .fillna(m["cur2"])
    .str.upper()
    .str.replace(" ", "", regex=False)
    .map(currency_map)
)


# 5) Betrag in Float umwandeln
def _parse_amount(raw: str) -> float | None:
    if not isinstance(raw, str):
        return 0.00
    s = raw.strip().replace("\u00a0", " ").replace("\u202f", " ")
    s = s.replace(".-", ".00")  # "123.-" → "123.00"
    digits = re.sub(r"[^\d,\.]", "", s)  # alles außer Ziffern, Punkt, Komma raus
    if "," in digits and "." in digits:
        if digits.rfind(",") > digits.rfind("."):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
    elif "," in digits:
        digits = digits.replace(".", "").replace(",", ".")
    else:
        digits = digits.replace(",", "")
    try:
        return round(float(digits), 2)
    except ValueError:
        return 0.00


df["preis_wert"] = m["amt"].map(_parse_amount).fillna(0.00)

# 6) Versandkosten vektorisiert extrahieren
df["versand_wert"] = (
    df["versand"]
    .astype(str)
    .str.extract(price_re)["amt"]
    .map(_parse_amount)
    .fillna(0.00)
)

print("Preise und Versandfelder (vektorisiert) extrahiert.\n")

# ----------------------------
# 4. Wechselkurse laden (API + Cache)
# ----------------------------

FX_CACHE_PATH = "Antonio_datacleansing/fx_cache.json"
API_URL = "https://open.er-api.com/v6/latest/CHF"
CURRENCIES = ["EUR", "USD", "GBP", "CHF"]


def load_fx_rates():
    """Lädt tagesaktuelle Wechselkurse oder nutzt Cache bei API-Ausfall."""
    try:
        # Cache prüfen
        try:
            with open(FX_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
                ts = datetime.fromisoformat(cache["timestamp"])
                if datetime.now() - ts < timedelta(hours=48):
                    print("Wechselkurse aus Cache geladen.\n")
                    return cache["rates"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass  # Kein Cache oder unbrauchbar

        # Neue Kurse abrufen
        print("Lade tagesaktuelle Wechselkurse von open.er-api.com ...")
        r = requests.get(API_URL, timeout=5)
        data = r.json()
        if "rates" not in data:
            raise ValueError("Ungültige API-Antwort")

        rates = {
            cur: round(1 / data["rates"][cur], 4) if cur != "CHF" else 1.0
            for cur in CURRENCIES
            if cur in data["rates"]
        }

        # Speichern im Cache
        with open(FX_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"timestamp": datetime.now().isoformat(), "rates": rates},
                f,
                ensure_ascii=False,
                indent=2,
            )

        print("Wechselkurse erfolgreich aktualisiert.\n")
        return rates

    except Exception as e:
        print(f"⚠️ API-Fehler: {e} – Verwende Default-Kurse.\n")
        return {"EUR": 0.95, "USD": 0.88, "GBP": 0.77, "CHF": 1.0}


# Tagesaktuelle oder gecachte Kurse laden
FX_RATES = load_fx_rates()


# ----------------------------
# 5. Preise in CHF konvertieren
# ----------------------------


def convert_to_chf(row) -> float:
    """Konvertiert Preis (inkl. Versand) in CHF.
    Nutzt tagesaktuelle FX_RATES, Fallback bei Fehlwerten."""
    rate = FX_RATES.get(row["waehrung"], 1.0)

    if not isinstance(row["preis_wert"], (int, float)) or row["preis_wert"] == 0.0:
        return 0.00

    versand = (
        row["versand_wert"] if isinstance(row["versand_wert"], (int, float)) else 0.0
    )
    total = row["preis_wert"] + versand
    return round(total / rate, 2)


# Neue Spalte mit Gesamtpreis in CHF
df["preis_total_chf"] = df.apply(convert_to_chf, axis=1)

print("Preise erfolgreich in CHF umgerechnet (API/Cache-Kurse verwendet).\n")

df["preis_total_chf"] = df["preis_total_chf"].round(2)
df["preis_wert"] = df["preis_wert"].round(2)
df["versand_wert"] = df["versand_wert"].round(2)

# ----------------------------
# 6. Länderbezeichnungen bereinigen
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
# 7. Produktstatus vereinheitlichen
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
# 7a. Duplikat-Vorbereitung: Strings normalisieren
# ----------------------------


def normalize_for_duplicates(text: str) -> str:
    """Vereinheitlicht Text für Duplikat-Erkennung (klein, ohne Sonderzeichen)."""
    if not isinstance(text, str):
        return ""
    text = unidecode(text.lower().strip())  # Kleinbuchstaben + Akzente weg
    text = re.sub(r"[^a-z0-9\s]", "", text)  # Sonderzeichen entfernen
    text = re.sub(r"\s+", " ", text)  # Mehrfache Leerzeichen reduzieren
    return text


# Normalisierte Hilfsspalte für Duplikaterkennung
df["titel_norm"] = df["titel"].apply(normalize_for_duplicates)
df["link_norm"] = df["link"].str.strip().str.lower()

print("Titel und Links für Duplikaterkennung normalisiert.\n")

# ----------------------------
# 8. Doppelte Einträge entfernen
# ----------------------------

df.drop_duplicates(subset=["titel_norm", "preis_total_chf", "link_norm"], inplace=True)
print("Doppelte Einträge entfernt (nach Normalisierung).\n")

# ----------------------------
# 9. Finale Struktur & Export
# ----------------------------

df.drop(columns=["titel_norm", "link_norm"], inplace=True, errors="ignore")

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
