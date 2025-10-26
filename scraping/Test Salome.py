#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from flask import Flask, render_template, request, redirect, url_for, session

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver
from bs4 import BeautifulSoup

# =============================================================================
# Flask + Pfade
# =============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

BASE_DIR = Path(__file__).resolve().parent

# ===== Input-Log (optional) =====
CSV_PATH = BASE_DIR / "data.csv"
CSV_FIELDS = ["Produkt", "Preis", "Region", "Link"]

# ===== Output Daten (Scraper) =====
CSV_DATA_PATH = BASE_DIR / "data_output.csv"
CSV_DATA_FIELDS = ["titel", "aktualitaet", "preis", "land", "versand", "link", "image"]

# =============================================================================
# Logging
# =============================================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ebay_scraper")


# =============================================================================
# CSV Utilities (Input-Log + Ergebnis-Ansicht)
# =============================================================================
def ensure_csv_with_header(path: Path, fields) -> None:
    """Erstellt CSV mit Header, falls sie nicht existiert oder leer ist."""
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()


def append_row(produkt_url: str, preis: str, region: str) -> None:
    """Hängt eine neue Zeile an das Eingaben-Log (data.csv) an."""
    ensure_csv_with_header(CSV_PATH, CSV_FIELDS)
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(
            {
                "Produkt": (produkt_url or "").strip(),
                "Preis": str(preis or "").strip(),
                "Region": (region or "").strip(),
                "Link": "",  # aktuell kein separater Link hier
            }
        )


def load_rows_for_table():
    """Liest die Scraper-CSV und liefert Zeilen fürs Template."""
    if not CSV_DATA_PATH.exists() or CSV_DATA_PATH.stat().st_size == 0:
        return []
    rows = []
    with CSV_DATA_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                {
                    "produkt": (r.get("titel") or "").strip(),
                    "preis": (r.get("preis") or "").strip(),
                    "region": (r.get("land") or "").strip(),  # Anzeige 'Region' = Land
                    "link": (r.get("link") or "").strip(),
                    "image": (r.get("image") or "").strip(),
                    "aktualitaet": (r.get("aktualitaet") or "").strip(),
                    "versand": (r.get("versand") or "").strip(),
                }
            )
    return rows


# =============================================================================
# Scraper-Konfiguration & Selektoren
# =============================================================================
BASE_URL = (
    "https://www.ebay.ch/sch/i.html?_nkw={}&_sacat=0&_from=R40&_trksid=m570.l1313"
)
MAX_PAGES = 10
HEADLESS = False  # nur für Chrome relevant

RESULTS_CONTAINER_SELECTOR = (
    ".srp-river-main, ul.srp-results, .srp-results, .s-card__grid, .srp-list"
)
ITEMS_SELECTOR = "li.s-card, div.s-card, li.s-item, div.s-item"
TITLE_SELECTOR = (
    ".s-card__title .su-styled-text.primary.default, "
    ".s-card__title [class*='su-styled-text'], "
    "[role='heading'].s-card__title, "
    ".s-item__title"
)
PRICE_SELECTOR = (
    ".s-card__attribute-row .s-card__price, "
    ".su-card-container__attributes__primary .s-card__price, "
    ".su-styled-text.primary.italic.large-1.s-card__price, "
    ".s-item__price"
)
ATTR_ROW_TEXTS_SELECTOR = (
    ".s-card__attribute-row .su-styled-text.secondary.italic.large, "
    ".s-card__attribute-row .su-styled-text.secondary.large, "
    ".s-item__location, "
    ".s-item__itemLocation"
)
CONDITION_SELECTOR = (
    ".s-card__subtitle-row .su-styled-text.secondary.default, "
    ".s-card__subtitle .su-styled-text.secondary.default, "
    ".SECONDARY_INFO, "
    ".s-item__subtitle .SECONDARY_INFO"
)
LINK_SELECTOR = "a.s-item__link, a[role='link'][href*='/itm/'], a[href*='/itm/']"
IMAGE_SELECTOR = "img.s-card__image, img.s-item__image-img, img.s-item__image"
NEXT_SELECTOR = ".pagination__next, a[rel='next'], a[aria-label='Weiter']"

TITLE_BAD_PHRASES = [
    "wird in neuem fenster oder tab geöffnet",
    "wird in neuem fenster geöffnet",
    "wird in einem neuen fenster oder tab geöffnet",
    "öffnet sich in einem neuen fenster oder tab",
    "opens in a new window or tab",
    "open in a new window or tab",
]
BAD_TITLE_SUBSTRINGS = [
    "shop on ebay",
    "shoppen auf ebay",
    "gesponsert",
    "sponsored",
    "anzeige",
    "advertisement",
    "ad:",
]


# =============================================================================
# WebDriver-Setup
# =============================================================================
def setup_driver(headless: bool = HEADLESS) -> WebDriver:
    """
    Windows (nt): Chrome (webdriver-manager)
    POSIX (macOS/Linux): Safari (wenn möglich), sonst Chrome (Fallback)
    """
    if os.name == "nt":
        logger.info("OS: Windows -> Chrome WebDriver")
        return _start_chrome(headless)
    elif os.name == "posix":
        logger.info("OS: POSIX -> versuche Safari, sonst Chrome")
        try:
            return _start_safari()
        except Exception:
            return _start_chrome(headless)
    else:
        raise RuntimeError(f"Unbekanntes Betriebssystem: {os.name}")


def _start_chrome(headless: bool) -> WebDriver:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager

    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1280, 900)
    return driver


def _start_safari() -> WebDriver:
    driver = webdriver.Safari()
    driver.set_window_size(1280, 900)
    return driver


# =============================================================================
# Scraper-Helfer
# =============================================================================
def accept_cookies(driver: WebDriver) -> None:
    """Versucht, Cookie-Banner (inkl. iframe) zu akzeptieren."""
    try:
        time.sleep(2)
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            txt = (btn.text or "").strip().lower()
            if any(
                k in txt
                for k in ("alle akzeptieren", "akzeptieren", "accept all", "accept")
            ):
                try:
                    btn.click()
                    logger.info("Cookie-Banner akzeptiert.")
                    time.sleep(0.8)
                    return
                except WebDriverException:
                    pass

        # iframe-Fallback
        for frame in driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                driver.switch_to.frame(frame)
                for btn in driver.find_elements(By.TAG_NAME, "button"):
                    txt = (btn.text or "").strip().lower()
                    if any(
                        k in txt
                        for k in (
                            "alle akzeptieren",
                            "akzeptieren",
                            "accept all",
                            "accept",
                        )
                    ):
                        try:
                            btn.click()
                            logger.info("Cookie-Banner (iframe) akzeptiert.")
                            time.sleep(0.8)
                        except WebDriverException:
                            pass
                        driver.switch_to.default_content()
                        return
                driver.switch_to.default_content()
            except WebDriverException:
                driver.switch_to.default_content()
    except Exception as e:
        logger.debug("Cookie-Banner Fehler: %s", e)


def wait_for_results(driver: WebDriver, timeout: int = 25) -> None:
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, RESULTS_CONTAINER_SELECTOR))
    )


def lazy_scroll(driver: WebDriver, steps: int = 6, pause: float = 0.8) -> None:
    last_h = 0
    for _ in range(steps):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        h = driver.execute_script("return document.body.scrollHeight;")
        if h == last_h:
            break
        last_h = h


def _sel_text(root: BeautifulSoup, selector: str) -> str:
    el = root.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


def _sel_href(root: BeautifulSoup, selector: str) -> Optional[str]:
    el = root.select_one(selector)
    if el and el.has_attr("href"):
        return el["href"].strip()
    return None


def _clean_title(title: str) -> str:
    if not title:
        return title
    t = title.strip()
    low = t.lower()
    for bad in TITLE_BAD_PHRASES:
        idx = low.find(bad)
        if idx != -1:
            t = t[:idx].rstrip(" -:–—•\u2022").strip()
            break
    return t


def _extract_location_and_shipping(card: BeautifulSoup) -> Tuple[str, str]:
    texts = [
        el.get_text(" ", strip=True)
        for el in card.select(ATTR_ROW_TEXTS_SELECTOR)
        if el.get_text(strip=True)
    ]
    land, versand = "", ""
    for t in texts:
        tl = t.lower()
        if ("versand" in tl) or t.strip().startswith("+"):
            if not versand:
                versand = t
            continue
        if ("aus " in tl) or ("from " in tl):
            if not land:
                land = t
            continue
    if not land and texts:
        candidates = [t for t in texts if "versand" not in t.lower()]
        if candidates:
            land = candidates[-1]
    if not land or "aus" not in land.lower():
        land = "aus Schweiz"
    return land, versand


def _parse_srcset_first(srcset: str) -> str:
    if not srcset:
        return ""
    parts = [p.strip() for p in srcset.split(",") if p.strip()]
    if not parts:
        return ""
    first = parts[0]
    return first.split()[0]


def _parse_src_value(val: str) -> str:
    if not val:
        return ""
    val = val.strip()
    if "," in val and " " in val:
        return _parse_srcset_first(val)
    return val


def _extract_image_url(img_el) -> str:
    """Bestmögliche Bild-URL aus einem <img>-Element."""
    if img_el is None:
        return ""
    src = img_el.get("src")
    if src:
        return src.strip()
    for attr in ("data-src", "data-img", "data-srcset", "data-lazy"):
        val = img_el.get(attr)
        if val:
            return _parse_src_value(val)
    srcset = img_el.get("srcset")
    if srcset:
        return _parse_srcset_first(srcset)
    return ""


# =============================================================================
# Kernparser + Scraper
# =============================================================================
def parse_items_from_html(html: str, seen_links: set) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(ITEMS_SELECTOR)
    rows: List[Dict] = []

    logger.info("Karten gefunden (ITEMS_SELECTOR): %d", len(cards))
    for card in cards:
        title = _clean_title(_sel_text(card, TITLE_SELECTOR)).strip()
        if not title:
            continue
        if any(bad in title.lower() for bad in BAD_TITLE_SUBSTRINGS):
            continue

        link = _sel_href(card, LINK_SELECTOR)
        if not link or "/itm/" not in link or link in seen_links:
            continue
        seen_links.add(link)

        price = _sel_text(card, PRICE_SELECTOR)
        condition = _sel_text(card, CONDITION_SELECTOR)
        land, versand = _extract_location_and_shipping(card)
        image_el = card.select_one(IMAGE_SELECTOR)
        image = _extract_image_url(image_el)

        rows.append(
            {
                "titel": title,
                "aktualitaet": condition,
                "preis": price,
                "land": land,
                "versand": versand,
                "link": link,
                "image": image,
            }
        )
    return rows


def scrape_all(
    driver: WebDriver, start_url: str, max_pages: int = MAX_PAGES
) -> List[Dict]:
    all_rows: List[Dict] = []
    current_url = start_url
    seen_links: set = set()

    for page in range(1, max_pages + 1):
        logger.info("Lade Seite %d: %s", page, current_url)
        driver.get(current_url)
        accept_cookies(driver)
        try:
            wait_for_results(driver, timeout=25)
        except TimeoutException:
            logger.warning(
                "Trefferliste nicht rechtzeitig erschienen – parse trotzdem …"
            )

        lazy_scroll(driver, steps=6, pause=0.8)
        html = driver.page_source

        if page == 1:
            with open(BASE_DIR / "debug_page1.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Debug gespeichert: debug_page1.html")

        page_rows = parse_items_from_html(html, seen_links)
        logger.info(" → %d verwertbare Angebote (nach Filter)", len(page_rows))
        if not page_rows and page == 1:
            logger.warning(
                "Keine Angebote geparst. Prüfe debug_page1.html und Selektoren."
            )
        all_rows.extend(page_rows)

        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one(NEXT_SELECTOR)
        if not next_link or not next_link.get("href"):
            logger.info("Keine weitere Seite gefunden.")
            break
        current_url = next_link["href"]
        time.sleep(1.1)

    return all_rows


def save_to_csv(items: List[Dict], filename: Path) -> None:
    ensure_csv_with_header(filename, CSV_DATA_FIELDS)
    with filename.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_DATA_FIELDS)
        w.writeheader()
        w.writerows(items)
    logger.info("CSV gespeichert: %s  (%d Zeilen)", filename, len(items))


def run_scrape(query: str) -> List[Dict]:
    """Öffentliche Funktion: Scrapen für einen Suchbegriff und CSV speichern."""
    start_url = BASE_URL.format(query)
    driver = setup_driver()
    try:
        rows = scrape_all(driver, start_url, max_pages=MAX_PAGES)
        save_to_csv(rows, CSV_DATA_PATH)
        return rows
    finally:
        try:
            driver.quit()
        except Exception:
            logger.debug("WebDriver konnte nicht sauber geschlossen werden.")


# =============================================================================
# Jinja-Filter
# =============================================================================
@app.template_filter("chf")
def chf_filter(value):
    """Formatiert Zahlen als Schweizer Franken, z. B. CHF 9'000."""
    try:
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return value
        n = int(digits)
        formatted = f"{n:,}".replace(",", "'")
        return f"CHF {formatted}"
    except Exception:
        return value


# =============================================================================
# Routes
# =============================================================================
@app.route("/")
def home():
    # Erwartet: templates/index.html
    return render_template("index.html", active_page="home")


@app.route("/submit", methods=["POST"])
def submit():
    produkt = request.form.get("produkt", "").strip()
    preis = request.form.get("preis", "").strip()
    region = request.form.get("region", "").strip()

    # Eingaben-Log (optional)
    append_row(produkt_url=produkt, preis=preis, region=region)

    # Scraper starten
    items = run_scrape(query=produkt)

    # Kurzinfo für UI
    session["new_row"] = {
        "produkt": produkt,
        "preis": preis,
        "region": region,
        "link": produkt,
    }
    session["scraped_count"] = len(items)
    return redirect(url_for("suchresultat_aktuell"))


@app.route("/suchresultat/aktuell")
def suchresultat_aktuell():
    """Zeigt nur den zuletzt gespeicherten Eintrag + Erfolgsmeldung."""
    new_row = session.pop("new_row", None)  # einmalig anzeigen
    scraped_count = session.pop("scraped_count", None)
    if not new_row:
        return redirect(url_for("suchresultat_total"))
    return render_template(
        "suchresultat_aktuell.html",
        daten=[new_row],
        message=f"Suchanfrage übernommen. {scraped_count or 0} Angebote gefunden.",
        success=True,
        active_page="results",
    )


@app.route("/suchresultat")
def suchresultat_total():
    """Alle gespeicherten Scraper-Einträge anzeigen."""
    daten = load_rows_for_table()
    return render_template(
        "suchresultat_total.html",
        daten=daten,
        active_page="results",
    )


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    # Header anlegen, falls Dateien fehlen
    ensure_csv_with_header(CSV_PATH, CSV_FIELDS)
    ensure_csv_with_header(CSV_DATA_PATH, CSV_DATA_FIELDS)
    app.run(debug=True)
