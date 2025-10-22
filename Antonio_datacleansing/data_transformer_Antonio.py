"""
Funktion:
1. CSV-Datei laden (Scraping-Daten)
2. Texte bereinigen (z. B. Umlautfehler, Sonderzeichen)
3. Preis und Währung trennen
4. Preise in CHF konvertieren (sofern nötig)
5. Doppelte Einträge entfernen
6. Einheitliche Struktur exportieren als clean_guitars_Antonio.csv

Abhängigkeiten:
- pandas
- unidecode
- flake8
"""

import pandas as pd
from unidecode import unidecode

# ----------------------------
# 1. CSV-Datei einlesen
# ----------------------------

# Pfad zur CSV-Datei (aus "scraper.py")
input_path = "Antonio_datacleansing/fake_scraped_guitars_Antonio.csv"
output_path = "Antonio_datacleansing/clean_guitars_Antonio.csv"

# CSV einlesen (Trennzeichen = Komma)
df = pd.read_csv(input_path)

# Kurze Übersicht der geladenen Daten
print("Datei erfolgreich geladen!")
print(f"Spalten: {list(df.columns)}")
print(f"Anzahl Zeilen: {len(df)}\n")

# ----------------------------
# 2. Texte bereinigen
# ----------------------------


# Funktion zur Textbereinigung
def clean_text(text):
    """
    Bereinigt Textfelder:
    - Entfernt fehlerhafte Kodierungen (z. B. ZÃ¼rich → Zürich)
    - Entfernt überflüssige Leerzeichen
    - Wandelt alles in Unicode lesbare Form um
    """
    if isinstance(text, str):
        text = unidecode(text)  # korrigiert Umlaute
        text = text.strip()  # entfernt Leerzeichen am Anfang/Ende
        return text
    return text


# Textspalten bereinigen
for column in ["Produkt", "Region", "Kategorie"]:
    df[column] = df[column].apply(clean_text)

print("Texte bereinigt (Umlaute, Leerzeichen etc.)\n")

# ----------------------------
# 3. Preis & Währung trennen
# ----------------------------


# Beispiel: "CHF 1'234.56" → Preis = 1234.56, Währung = CHF
def split_price(value):
    """
    Trennt Preis und Währung.
    Entfernt Kommas, Apostrophe und konvertiert in float.
    """
    if not isinstance(value, str):
        return None, None

    value = value.replace("'", "").replace(",", ".").strip()
    parts = value.split(" ")

    if len(parts) == 2:
        currency, price = parts
    elif "CHF" in value:
        currency, price = "CHF", value.replace("CHF", "")
    elif "EUR" in value:
        currency, price = "EUR", value.replace("EUR", "")
    else:
        return None, None

    try:
        price = float(price)
    except ValueError:
        price = None

    return currency, price


# Neue Spalten anlegen
df[["Waehrung", "Preis_Wert"]] = df["Preis"].apply(lambda x: pd.Series(split_price(x)))

print("Preise und Währungen getrennt\n")

# ----------------------------
# 4. Preise in CHF konvertieren
# ----------------------------

# Einfacher Umrechnungsfaktor (EUR → CHF)
EUR_TO_CHF = 0.95  # Beispielkurs


def convert_to_chf(row):
    """
    Wandelt Preise in CHF um, falls sie in EUR angegeben sind.
    """
    if row["Waehrung"] == "EUR" and row["Preis_Wert"] is not None:
        return round(row["Preis_Wert"] / EUR_TO_CHF, 2)
    else:
        return row["Preis_Wert"]


df["Preis_CHF"] = df.apply(convert_to_chf, axis=1)

print("Alle Preise auf CHF vereinheitlicht\n")

# ----------------------------
# 5. Doppelte Einträge entfernen
# ----------------------------

df.drop_duplicates(subset=["Produkt", "Preis_CHF", "Region"], inplace=True)
print("Doppelte Datensätze entfernt\n")

# ----------------------------
# 6. Finale Struktur & Export
# ----------------------------

# Relevante Spalten in neuer Reihenfolge
clean_df = df[["id", "Produkt", "Preis_CHF", "Region", "Kategorie", "Link"]]

# Export als neue CSV-Datei
clean_df.to_csv(output_path, index=False, encoding="utf-8")
print(f"Bereinigung abgeschlossen. Neue Datei gespeichert unter: {output_path}\n")

# ----------------------------
# 7. Abschlussmeldung
# ----------------------------

print("data_transformer.py erfolgreich abgeschlossen – Daten sind bereit für app.py!")

# ----------------------------
# Sicherer Einstiegspunkt
# ----------------------------
if __name__ == "__main__":
    print("Script wurde direkt ausgeführt – Datenbereinigung erfolgreich beendet.")
