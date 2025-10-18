#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL-basierte Paginierung für die eBay-Kategorie "Reisegitarren".
Speichert CSV mit Feldern: id, title, price, condition, link.
"""

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
BASE_URL = "https://www.ebay.ch/b/Reisegitarren/159948/bn_7204344"
OUTPUT_CSV = "reisegitarren_paginated.csv"
HEADLESS = False
WAIT_TIMEOUT = 6  # Sekunden: Wartezeit nach driver.get()
PAGE_PARAM_NAME = "_pgn"  # Parametername in der URL
MAX_PAGES = 20  # wie viele Seiten maximal abarbeiten
MAX_ITEMS = 1000  # Sicherheitslimit: max. zu speichernde Items insgesamt
DELAY_BETWEEN_PAGES = 1.2  # Sekunden Pause zwischen Seiten (politely)
# Selektoren (können angepasst / verfeinert werden)
ITEMS_SELECTOR = "li.brwrvr__item-card"
TITLE_SELECTOR = "h3"
PRICE_SELECTOR = "span.s-item__price"
CONDITION_SELECTOR = "span.bsig__listingCondition"
LINK_SELECTOR = "a[href*='/itm/']"
# ---------------------------------------------------------

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ebay_pager")


def init_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1200")
    # optional: user-agent
    opts.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver


def build_page_url(base_url: str, page_number: int) -> str:
    """
    Baut eine URL mit ?_pgn=<page_number>&rt=nc (falls nicht vorhanden).
    Erhält vorhandene Query-Parameter (falls vorhanden).
    """
    parsed = urlparse(base_url)
    qs = parse_qs(parsed.query)
    qs[PAGE_PARAM_NAME] = [str(page_number)]
    # häufig ist rt=nc gewünscht; fügen wir hinzu, wenn nicht vorhanden
    if "rt" not in qs:
        qs["rt"] = ["nc"]
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def extract_items_from_html(html: str) -> List[Dict[str, str]]:
    """
    Parst HTML (BeautifulSoup) und gibt Liste von Dicts mit id,title,price,condition,link.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(ITEMS_SELECTOR)
    results: List[Dict[str, str]] = []
    for item in items:
        title_el = item.select_one(TITLE_SELECTOR)
        price_el = item.select_one(PRICE_SELECTOR)
        condition_el = item.select_one(CONDITION_SELECTOR)
        link_el = item.select_one(LINK_SELECTOR)

        title = title_el.get_text(strip=True) if title_el else ""
        price = price_el.get_text(strip=True) if price_el else ""
        condition = condition_el.get_text(strip=True) if condition_el else ""
        link = link_el["href"] if link_el and link_el.has_attr("href") else ""

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
                    "link": link,
                }
            )
    return results


def save_csv(filename: str, rows: List[Dict[str, str]]):
    fieldnames = ["id", "title", "price", "condition", "link"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    logger.info("CSV geschrieben: %s (Zeilen: %d)", filename, len(rows))


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

            # kurze Wartezeit, damit dynamische Elemente geladen werden
            time.sleep(WAIT_TIMEOUT)

            html = driver.page_source
            page_items = extract_items_from_html(html)
            logger.info("Gefundene Items auf Seite %d: %d", page, len(page_items))

            # Falls keine Items gefunden werden, kann das Ende erreicht sein
            if not page_items:
                logger.info("Keine Items auf Seite %d — Abbruch der Pagination.", page)
                break

            # neue Items zur Gesamtliste hinzufügen (Duplikate vermeiden)
            # einfacher Schutz: vermeide Items mit gleicher ID
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

            # Abbruchbedingungen
            if len(all_results) >= MAX_ITEMS:
                logger.info("MAX_ITEMS erreicht (%d). Stoppe.", MAX_ITEMS)
                all_results = all_results[:MAX_ITEMS]
                break

            # Pause zwischen den Seiten (politely)
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
