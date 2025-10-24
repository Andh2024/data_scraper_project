#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Daten-Transformer für Pricehunter
---------------------------------
Liest 'scraping_output.csv' aus dem gleichen Ordner wie dieses Skript
und schreibt die bereinigte Datei als 'output_clean.csv' zurück.

Umfang der Transformation:
- title:
    * Spalte 'Titel'/'title' wird in 'title' umbenannt, Werte unverändert.
- Zustand:
    * Entfernt ein finales ' |' (falls vorhanden).
    * Leere Werte -> 'keine Angabe'.
    * Spaltenname: 'product_condition'.
- Preis:
    * Extrahiert numerischen Betrag (EU-Format wird erkannt, z.B. 3.040,06).
    * Währung wird separat als 'currency' ausgewiesen.
    * Neue Spalten: 'price' (float) und 'currency' (z.B. EUR/CHF/USD/GBP).
- Land:
    * Entfernt führendes 'aus ' -> nur das Land bleibt übrig.
    * Spaltenname: 'product_origin'.
    * Korrigiert fehlerhaft encodiertes 'Großbritannien' (z.B. 'GroÃŸbritannien')
      zu 'Grossbritannien'.
- Versandkosten:
    * Extrahiert numerischen Betrag analog 'price', ohne '+'/'Versand'/Währung.
    * Neue Spalten:
        - 'shipping_cost' (float oder 'keine Angabe', wenn nichts da)
        - 'price_with_shipping' (Summe aus 'price' + 'shipping_cost' oder
          'keine Angabe', falls unvollständig)
    * Falls 'currency' in 'price' nicht erkennbar ist, wird – falls möglich –
      die Währung aus den Versandkosten übernommen.
- product_name:
    * Aus der *ersten* URL-Spalte den Query-Parameter 'skw' oder '_skw'
      extrahieren (alles vor 'skw=' sowie alles nach dem nächsten '&' wird
      entfernt). URL-decodiert. Erster Buchstabe wird groß gemacht.
      Wenn nicht vorhanden -> 'keine Angabe'.

Das Skript ist bewusst robust gegenüber leicht unterschiedlichen Spaltennamen
(z.B. 'Preis'/'price', 'Versand'/'Versandkosten', usw.).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
import re
import sys
import pandas as pd


# ----------------------------- Definition Funktionen ----------------------------- #


# Spaltennamen suchen und wiedergeben
def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    Sucht die erste Spalte im DataFrame, deren Name einem der Kandidaten
    (case-insensitive) entspricht, und gibt den *exakten* Spaltennamen zurück.
    """
    mapping = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in mapping:
            return mapping[cand.lower()]
    return None


CURRENCY_MAP = {
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "chf": "CHF",
    "sfr": "CHF",
    "fr.": "CHF",
    "fr": "CHF",
    "$": "USD",
    "usd": "USD",
    "£": "GBP",
    "gbp": "GBP",
}


# Währung aus Text extrahieren
def extract_currency(text: str | float | int | None) -> str | None:
    """
    Versucht, eine Währung aus dem gegebenen Text zu erkennen.
    Gibt ISO-ähnliche Kürzel (EUR/CHF/USD/GBP) zurück oder None.
    """
    if text is None:
        return None
    s = str(text).lower()
    for key, code in CURRENCY_MAP.items():
        if key in s:
            return code
    return None


# Preise normalisieren
def parse_number_eu(text: str | float | int | None) -> float | None:
    """
    Parst europäische/„gemischte“ Zahlendarstellungen in float.
    Beispiele:
        "3.040,06" -> 3040.06
        "1,234"    -> 1.234  (interpretiert Komma als Dezimalzeichen, wenn
                               plausible Stellenanzahl)
        "1.234"    -> 1234.0 (Punkt als Tausender)
        "+ 12,00 EUR Versand" -> 12.0
    Gibt None zurück, wenn es nicht parsebar ist.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None

    # Störwörter/Zeichen entfernen (ohne Ziffern/.,,)
    s = re.sub(
        r"(versand|inkl\.?|exkl\.?|inklusive|zzgl\.?|\+)", " ", s, flags=re.IGNORECASE
    )
    s = re.sub(r"[^0-9\.,\s]", "", s)  # nur Ziffern, Punkt, Komma, Space

    s = s.strip()
    if not s:
        return None

    # Heuristik: wenn beides vorkommt, '.' als Tausender, ',' als Dezimal
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Prüfe, ob das letzte Segment Dezimalstellen sein könnten
        parts = s.split(",")
        if len(parts[-1]) in (2, 3):
            s = "".join(parts[:-1]).replace(".", "") + "." + parts[-1]
        else:
            # eher Tausendertrennzeichen
            s = s.replace(",", "")
    else:
        # nur Punkte -> so belassen (kann Dezimalpunkt oder Integer sein)
        pass

    s = s.replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


# Korrigiert fehlerhafte Darstellung von 'Grossbritannien'
def fix_grossbritannien(value: str | None) -> str | None:
    """
    Korrigiert fehlerhafte Encodings von 'Großbritannien' auf 'Grossbritannien'.
    Wir ändern *nur* bekannte defekte Varianten.
    """
    if value is None:
        return None
    s = str(value).strip()
    bad = {
        "GroÃŸbritannien",
        "GroÃbritannien",
        "GroÃ£Âbritannien",
        "Großbritannien",
    }
    if s in bad:
        return "Grossbritannien"
    return s


# Produktname aus URL extrahieren
def find_first_url_column(df: pd.DataFrame) -> str | None:
    """
    Sucht die erste Spalte, die wie eine URL-Spalte aussieht (enthält 'http').
    """
    for col in df.columns:
        series = df[col].astype(str)
        if series.str.contains(r"https?://", regex=True, na=False).any():
            return col
    return None


def extract_skw_from_url(url: str | None) -> str | None:
    """
    Extrahiert den Wert des Query-Parameters 'skw' oder '_skw' aus einer URL
    und gibt ihn URL-decodiert zurück. Bei Erfolg wird nur der *erste Buchstabe*
    groß geschrieben; der Rest bleibt unverändert.
    """
    if not url:
        return None
    try:
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        key = "skw" if "skw" in query else "_skw" if "_skw" in query else None
        if not key:
            return None
        raw = query[key][0]
        text = unquote(raw).strip()
        if not text:
            return None
        return text[:1].upper() + text[1:]
    except Exception:
        return None


# ----------------------------- Hauptlogik Transformation ---------------------------------- #


def transform(input_path: Path, output_path: Path) -> None:
    """
    Führt sämtliche Transformationen aus und schreibt die bereinigte CSV.
    """
    # 1) CSV laden – robust gegen Encoding-Probleme
    try:
        df = pd.read_csv(input_path)
    except UnicodeDecodeError:
        df = pd.read_csv(input_path, encoding="latin-1")

    out = df.copy()

    # 2) Spalten ermitteln (tolerant gegenüber Varianten)
    col_title = find_col(out, ["Titel", "title", "Title"])
    col_state = find_col(out, ["Zustand", "zustand", "Condition", "condition"])
    col_price = find_col(out, ["Preis", "preis", "Price", "price"])
    col_country = find_col(
        out, ["Land", "land", "Country", "country", "Herkunft", "herkunft"]
    )
    col_ship = find_col(
        out,
        [
            "Versandkosten",
            "versandkosten",
            "Versand",
            "versand",
            "Shipping",
            "shipping",
        ],
    )

    # 3) title
    if col_title:
        out = out.rename(columns={col_title: "title"})
    else:
        # Falls keine Titel-Spalte existiert, legen wir eine leere an.
        out["title"] = ""

    # 4) Zustand -> product_condition
    if col_state:
        cond = out[col_state].astype(str)
        cond = cond.replace(["nan", "NaN", "None"], "", regex=False)
        cond = cond.str.replace(r"\s*\|\s*$", "", regex=True)  # ' |' am Ende
        cond = cond.str.strip().replace("", "keine Angabe")
        out["product_condition"] = cond
        out.drop(columns=[col_state], inplace=True)

    # 5) Land -> product_origin (+ 'aus ' entfernen + GB-Korrektur)
    if col_country:
        origin = out[col_country].astype(str)
        origin = origin.replace(["nan", "NaN", "None"], "", regex=False)
        origin = origin.str.replace(r"^\s*aus\s+", "", flags=re.IGNORECASE, regex=True)
        origin = origin.map(fix_grossbritannien)
        origin = origin.str.strip()
        out["product_origin"] = origin
        out.drop(columns=[col_country], inplace=True)
    else:
        # Falls keine Länderspalte vorhanden ist, legen wir sie leer an.
        out["product_origin"] = ""

    # 6) Preis -> price + currency
    if col_price:
        price_text = out[col_price].astype(str)
        price_num = price_text.map(parse_number_eu)
        curr_series = price_text.map(extract_currency)

        out["price"] = price_num
        out["currency"] = curr_series
        out.drop(columns=[col_price], inplace=True)
    else:
        out["price"] = pd.NA
        out["currency"] = pd.NA

    # 7) Versandkosten -> shipping_cost + price_with_shipping
    shipping_numeric = None
    if col_ship:
        ship_text = out[col_ship].astype(str)

        # Falls 'currency' noch fehlt, dort versuchen zu ermitteln.
        ship_currency = ship_text.map(extract_currency)
        out["currency"] = out["currency"].fillna(ship_currency)

        shipping_numeric = ship_text.map(parse_number_eu)
        out["shipping_cost"] = shipping_numeric.where(
            shipping_numeric.notna(), other="keine Angabe"
        )

        # price_with_shipping (nur wenn beide Zahlen vorhanden)
        def combine(p, s):
            if pd.notna(p) and pd.notna(s):
                return float(p) + float(s)
            return "keine Angabe"

        out["price_with_shipping"] = [
            combine(out["price"].iat[i], shipping_numeric.iat[i])
            for i in range(len(out))
        ]

        out.drop(columns=[col_ship], inplace=True)
    else:
        out["shipping_cost"] = "keine Angabe"
        out["price_with_shipping"] = "keine Angabe"

    # 8) currency: verbleibende Nullen -> 'keine Angabe'
    out["currency"] = out["currency"].fillna("keine Angabe")

    # 9) product_name: aus erster URL-Spalte skw/_skw extrahieren
    url_col = find_first_url_column(out)
    if url_col:
        prod_name = out[url_col].map(extract_skw_from_url)
        out["product_name"] = prod_name.fillna("keine Angabe")
    else:
        out["product_name"] = "keine Angabe"

    # 10a) Spaltenreihenfolge harmonisieren (falls vorhanden)
    desired_order = [
        "title",
        "product_condition",
        "price",
        "currency",
        "product_origin",
        "shipping_cost",
        "price_with_shipping",
        "product_name",
    ]
    existing = [c for c in desired_order if c in out.columns]
    remaining = [c for c in out.columns if c not in existing]
    out = out[existing + remaining]
    # 10b) Zusätzliche Spaltennamen anpassen (z.B. Link, Link zum Bild)
    rename_map = {}
    for col in out.columns:
        col_lower = col.lower().strip()
        if col_lower == "link":
            rename_map[col] = "link"
        elif col_lower in ["link zum bild", "link_zum_bild"]:
            rename_map[col] = "link_bild"
    if rename_map:
        out = out.rename(columns=rename_map)

    # 11) Schreiben
    out.to_csv(output_path, index=False)
    print(f"✅ Fertig: {output_path}")


# Startpunkt des Skripts
def main() -> None:
    """
    Bestimmt Ein- und Ausgabepfade:
    - 'scraping_output.csv' liegt im Projekt-Root (eine Ebene über 'datacleansing')
    - Ausgabe 'output_clean.csv' wird im selben Ordner gespeichert
    """
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent  # eine Ebene höher

    # Pfade setzen
    input_path = project_root / "scraping_output.csv"
    output_path = project_root / "output_clean.csv"

    if not input_path.exists():
        print(f"❌ Eingabedatei nicht gefunden: {input_path}", file=sys.stderr)
        sys.exit(1)

    transform(input_path, output_path)


if __name__ == "__main__":
    main()
