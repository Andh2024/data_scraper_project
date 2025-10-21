#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import csv
import time
import logging
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# -------------------- Konfiguration --------------------
START_URL = "https://www.ebay.ch/b/Reisegitarren/159948/bn_7204344"
OUTPUT_CSV = "scraping_ebay_windows.csv"
HEADLESS = False  # Für Entwicklung: False (sichtbar). Produktion: True
WAIT_TIME = 2  # Sekunden Wartezeit nach Aktionen
WAIT_TIMEOUT = 18  # Sekunden für WebDriverWait
MAX_ITEMS = 500  # Schutzlimit: max. zu speichernde Items
# Robuste Selektoren (mehrere Alternativen, Komma-getrennt)
ITEMS_SELECTOR = "li.brwrvr__item-card, li.brwrvr__item-card--list, li.s-item, .s-item"
TITLE_SELECTOR = "span.bsig__title"
PRICE_SELECTOR = "span.bsig__price--displayprice"
LINK_SELECTOR = "a.s-item__link, a[href*='/itm/'], a"
CONDITION_SELECTOR = "span.bsig__listingCondition"
# -------------------------------------------------------

# Log für Anzeige im Terminal konfigurieren. Logging Level INFO kann angepasst werden mit DEBUG (detaillierter), WARNING oder ERROR (weniger detailliert).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ebay_scraper")


# Chrome WebDriver initialisieren
def init_driver(
    headless: bool = True,
) -> webdriver.Chrome:  # wenn bool = false, dann läuft der Browser sichtbar
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1200")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )  # Generische User-Agent (so kann man sich selber identifizieren)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# Cookie-Banner erkennen und schliessen
def try_click(element, driver) -> bool:
    """Versuche Klick normal, sonst JS-Fallback."""
    for click_method in [
        element.click,
        lambda: driver.execute_script("arguments[0].click();", element),
    ]:
        try:
            click_method()
            return True
        except Exception:
            continue
    return False


def dismiss_cookie_banner(driver, timeout: int = 8) -> bool:
    """Schließt automatisch Cookie-Banner, falls vorhanden."""
    logger.info("Versuche Cookie-Banner zu schließen...")
    candidates = [
        "button[aria-label*='accept']",
        "button[aria-label*='Accept']",
        "button[aria-label*='Akzeptieren']",
        "button[class*='accept']",
        "button[class*='cookie']",
        "//button[contains(text(),'Accept')]",
        "//button[contains(text(),'Akzeptieren')]",
        "//div[contains(@class,'cookie')]//button",
    ]
    for sel in candidates:
        try:
            els = (
                driver.find_elements(By.CSS_SELECTOR, sel)
                if not sel.startswith("//")
                else driver.find_elements(By.XPATH, sel)
            )
            for el in els:
                if try_click(el, driver):
                    logger.info("Cookie-Banner geschlossen: %s", sel)
                    return True
        except Exception:
            continue
    return False


# Daten scrapen
def extract_items(driver) -> List[Dict[str, str]]:
    time.sleep(WAIT_TIME)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(ITEMS_SELECTOR)
    results = []

    for item in items:
        title_el = item.select_one(TITLE_SELECTOR)
        price_el = item.select_one(PRICE_SELECTOR)
        condition_el = item.select_one(CONDITION_SELECTOR)
        link_el = item.select_one(LINK_SELECTOR)

        title = title_el.get_text(strip=True) if title_el else ""
        price = price_el.get_text(strip=True) if price_el else ""
        condition = condition_el.get_text(strip=True) if condition_el else ""
        link = link_el["href"] if link_el else ""

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
                    "link": link,
                }
            )

    logger.info("Extrahierte Artikel: %d", len(results))
    return results


# Versuch, Seite zu scrollen
def scroll_page(driver, max_items=500):
    """Scrollt die Seite nach unten, bis alle Artikel geladen oder max_items erreicht sind."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(WAIT_TIME)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            logger.info("Ende der Seite erreicht oder keine neuen Artikel.")
            break
        last_height = new_height
        # Optional: stoppe, wenn max_items erreicht
        current_items = len(driver.find_elements(By.CSS_SELECTOR, ITEMS_SELECTOR))
        if current_items >= max_items:
            logger.info("MAX_ITEMS erreicht: %d", current_items)
            break


# Daten in csv speichern
def save_csv(filename: str, rows: List[Dict[str, str]]):
    """Speichert die Daten in einer CSV-Datei."""
    fieldnames = ["id", "title", "price", "condition", "link"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    logger.info("CSV gespeichert: %s", filename)


# Hauptfunktion
def main():
    driver = init_driver(HEADLESS)
    all_rows = []
    try:
        driver.get(START_URL)
        dismiss_cookie_banner(driver)
        scroll_page(driver, MAX_ITEMS)
        all_rows = extract_items(driver)
        if len(all_rows) > MAX_ITEMS:
            all_rows = all_rows[:MAX_ITEMS]

    finally:
        driver.quit()

    if all_rows:
        save_csv(OUTPUT_CSV, all_rows)
    else:
        logger.info(
            "Keine Daten extrahiert. Prüfen Sie Selektoren oder Netzwerkzugang."
        )


if __name__ == "__main__":
    main()
