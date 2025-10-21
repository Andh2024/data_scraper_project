#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import csv
import logging
from typing import List, Dict
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ---------------- Konfiguration (anpassen) ----------------
BASE_URL = "https://www.ebay.ch/b/Akustik-Westerngitarren/33021/bn_2394951"
OUTPUT_CSV = "reisegitarren_paginated.csv"
HEADLESS = False  # Für Entwicklung: False (sichtbar). Produktion: True
WAIT_TIMEOUT = 12  # Sekunden: Wartezeit nach driver.get()
PAGE_PARAM_NAME = "_pgn"  # Parametername für Seitenzählung in der URL
MAX_PAGES = 1  # wie viele Seiten maximal abarbeiten
MAX_ITEMS = 1000  # Sicherheitslimit: max. zu speichernde Items insgesamt
DELAY_BETWEEN_PAGES = 1.2  # Sekunden Pause zwischen Seiten (politely)
# Selektoren (können angepasst / verfeinert werden)
ITEMS_SELECTOR = "li.brwrvr__item-card"
TITLE_SELECTOR = "h3"
PRICE_SELECTOR = "span.bsig__price--displayprice"
CONDITION_SELECTOR = "span.bsig__listingCondition"
LOCATION_SELECTOR = (
    "span.ux-textspans.ux-textspans--SECONDARY"  # Listenansicht-Selektor
)
LINK_SELECTOR = "a[href*='/itm/']"
# ---------------------------------------------------------

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ebay_pager")


# Chrome WebDriver initialisieren
def init_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1200")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver


# URL für eine bestimmte Seite bauen
def build_page_url(base_url: str, page_number: int) -> str:
    parsed = urlparse(base_url)
    qs = parse_qs(parsed.query)
    qs[PAGE_PARAM_NAME] = [str(page_number)]
    if "rt" not in qs:
        qs["rt"] = ["nc"]
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


# Hilfsfunktion: Standorttext bereinigen
def clean_location_text(txt: str) -> str:
    if not txt:
        return ""
    t = txt.strip()
    t = re.sub(r"(?i)\b(standort:|location:|located in:)\b", "", t)
    return " ".join(t.split())


# ----- NEU: Detailabruf-Funktion -----
def get_item_location_from_detail(
    driver: webdriver.Chrome, link: str, timeout: float = 2.0
) -> str:
    """
    Öffnet die Artikelseite in einem neuen Tab, extrahiert den Standort anhand
    mehrerer möglicher Selektoren und schliesst das Tab wieder.
    Liefert den bereinigten Standort-String oder "" wenn nichts gefunden.
    Hinweis: Dieser Aufruf ist relativ langsam, verwenden Sie ihn nur für Items ohne Location in der Listenansicht.
    """
    if not link:
        return ""

    original_handle = None
    try:
        original_handle = driver.current_window_handle
    except Exception:
        original_handle = None

    try:
        # Neues Tab öffnen und darauf wechseln
        driver.execute_script("window.open('');")
        handles = driver.window_handles
        new_handle = (
            [h for h in handles if h != original_handle][-1]
            if original_handle in handles
            else handles[-1]
        )
        driver.switch_to.window(new_handle)

        # Lade die Artikelseite
        driver.get(link)
        time.sleep(timeout)  # kurze Wartezeit, damit Seite lädt

        # Page-Source parsen
        page_html = driver.page_source
        psoup = BeautifulSoup(page_html, "html.parser")

        # Mögliche Selektoren auf der Detailseite (inkl. der von Ihnen gewünschten Klasse)
        detail_selectors = [
            "span.ux-textspans.ux-textspans--SECONDARY",  # Ihre angegebene Variante
            "span.ux-textspans.ux-testspans--SECONDARY",  # alternative / typo-Variante
            "#itemLocation",
            ".iti-eu-bld-gry",
            ".item-location",
            "[data-test-id*='item-location']",
            ".u-flL .sh-loc",
            "span.s-item__shipping",  # fallback, manchmal enthalten
        ]

        for ds in detail_selectors:
            try:
                el = psoup.select_one(ds)
                if el and el.get_text(strip=True):
                    loc = clean_location_text(el.get_text(" ", strip=True))
                    return loc
            except Exception:
                continue

        # Fallback: Suche im Rohtext der Seite nach "Standort" o.ä.
        full_text = psoup.get_text(" ", strip=True)[:5000]  # nur Anfangstext
        m = re.search(
            r"(Standort[:\s]*[A-Za-zÄÖÜäöü0-9,\-\s]+|Located in[:\s]*[A-Za-z0-9,\-\s]+)",
            full_text,
            flags=re.IGNORECASE,
        )
        if m:
            loc = clean_location_text(m.group(0))
            return loc

    except Exception as e:
        logger.debug("Fehler beim Detailabruf (%s): %s", link, e)
        # continue to finally to close tab and switch back
    finally:
        # Schließe das neue Tab, falls vorhanden, und wechsle zurück
        try:
            current = driver.current_window_handle
            if original_handle and current != original_handle:
                driver.close()
                driver.switch_to.window(original_handle)
            elif not original_handle:
                # falls kein original_handle bekannt, versuche, zum ersten handle zu wechseln
                handles = driver.window_handles
                if handles:
                    driver.switch_to.window(handles[0])
        except Exception:
            # Wenn das Schließen/Wechseln fehlschlägt, lassen wir es stillschweigend passieren
            pass

    return ""


# Daten scrapen (HTML analysieren)
def extract_items_from_html(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(ITEMS_SELECTOR)
    results: List[Dict[str, str]] = []

    for item in items:
        title_el = item.select_one(TITLE_SELECTOR)
        price_el = item.select_one(PRICE_SELECTOR)
        condition_el = item.select_one(CONDITION_SELECTOR)
        location_el = item.select_one(LOCATION_SELECTOR)  # Listenansicht-Selektor
        link_el = item.select_one(LINK_SELECTOR)

        title = title_el.get_text(strip=True) if title_el else ""
        price = price_el.get_text(strip=True) if price_el else ""
        condition = condition_el.get_text(strip=True) if condition_el else ""
        location = (
            clean_location_text(location_el.get_text(strip=True)) if location_el else ""
        )
        link = link_el["href"] if link_el and link_el.has_attr("href") else ""

        # Item-ID aus URL extrahieren
        item_id = ""
        if link:
            m = re.search(r"/itm/(?:.*?/)?(\d{6,})", link)
            if m:
                item_id = m.group(1)

        if item_id or title:
            results.append(
                {
                    "id": item_id,
                    "title": title,
                    "price": price,
                    "condition": condition,
                    "location": location,
                    "link": link,
                }
            )
    return results


# CSV speichern
def save_csv(filename: str, rows: List[Dict[str, str]]):
    fieldnames = ["id", "title", "price", "condition", "location", "link"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    logger.info("CSV geschrieben: %s (Zeilen: %d)", filename, len(rows))


# Hauptfunktion
def main():
    driver = init_driver(HEADLESS)
    all_results: List[Dict[str, str]] = []
    try:
        for page in range(1, MAX_PAGES + 1):
            url = build_page_url(BASE_URL, page)
            logger.info("Seite %d laden: %s", page, url)
            try:
                driver.get(url)
            except Exception as e:
                logger.warning("Fehler beim Laden der URL: %s", e)
                break

            time.sleep(WAIT_TIMEOUT)
            html = driver.page_source
            page_items = extract_items_from_html(html)
            logger.info("Gefundene Items auf Seite %d: %d", page, len(page_items))

            if not page_items:
                logger.info("Keine Items auf Seite %d — Abbruch der Pagination.", page)
                break

            # Für Items ohne location: Detailseite abfragen (langsam)
            for it in page_items:
                if not it.get("location") and it.get("link"):
                    # kurzer, konservativer Timeout; erhöhen Sie bei Bedarf
                    loc = get_item_location_from_detail(driver, it["link"], timeout=2.0)
                    if loc:
                        it["location"] = loc
                        logger.debug(
                            "Detail-Location gefunden für %s: %s",
                            it.get("id") or it.get("title"),
                            loc,
                        )
                    # kleine Pause, um Server nicht zu belasten
                    time.sleep(0.35)

            # neue Items zur Gesamtliste hinzufügen (Duplikate vermeiden)
            existing_ids = {r["id"] for r in all_results if r.get("id")}
            new_added = 0
            for it in page_items:
                if it.get("id") and it["id"] in existing_ids:
                    continue
                all_results.append(it)
                if it.get("id"):
                    existing_ids.add(it["id"])
                new_added += 1

            logger.info(
                "Neue Items hinzugefügt: %d — Total bisher: %d",
                new_added,
                len(all_results),
            )

            if len(all_results) >= MAX_ITEMS:
                logger.info("MAX_ITEMS erreicht (%d). Stoppe.", MAX_ITEMS)
                all_results = all_results[:MAX_ITEMS]
                break

            time.sleep(DELAY_BETWEEN_PAGES)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if all_results:
        save_csv(OUTPUT_CSV, all_results)
    else:
        logger.info(
            "Keine Daten extrahiert. Prüfen Sie Selektoren / Netzwerk / robots.txt."
        )


if __name__ == "__main__":
    main()
