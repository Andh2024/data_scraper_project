import csv
import os
from pathlib import Path
import os
import time
import csv
from typing import List, Dict, Optional, Tuple
import logging
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver


from bs4 import BeautifulSoup

# from typing import List, Dict, Any

from flask import Flask, render_template, request, redirect, url_for, session

# from scraper_ebay import main

# -----------------------------------------------------------------------------
# Flask-App
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ===== Input Daten =====

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data.csv"
REGION_COLOR_FILE = BASE_DIR / "region_colors.json"

CSV_FIELDS = ["Produkt", "Preis", "Region", "Link"]

# ===== Output Daten =====

CSV_DATA_PATH = Path("data_output.csv")
CSV_DATA_PATH = BASE_DIR / "data_output.csv"
CSV_DATA_FIELDS = ["Produkt", "Link", "Preis", "Region"]


# -----------------------------------------------------------------------------
# CSV Utilities
# -----------------------------------------------------------------------------
def ensure_csv_with_header() -> None:
    """Erstellt data.csv mit Header, falls sie nicht existiert oder leer ist."""
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def append_row(produkt_url: str, preis: str, region: str) -> None:
    """Hängt eine neue Zeile an die CSV an."""
    ensure_csv_with_header()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(
            {
                "Produkt": (produkt_url or "").strip(),
                "Preis": str(preis or "").strip(),
                "Region": (region or "").strip(),
                # Link = Produkt-URL (gemäss aktueller Datenstruktur)
                "Link": "",
            }
        )


def load_rows_for_table():
    """Liest CSV und liefert Zeilen im Format für die Tabelle (zeile.*)."""
    if not CSV_DATA_PATH.exists() or CSV_DATA_PATH.stat().st_size == 0:
        return []
    rows = []
    with CSV_DATA_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            produkt = (r.get("Produkt") or "").strip()
            preis = (r.get("Preis") or "").strip()
            region = (r.get("Region") or "").strip()
            produkt_url = (r.get("Link") or "").strip()
            rows.append(
                {
                    "produkt": produkt,
                    "preis": preis,
                    "region": region,
                    "link": produkt_url,
                }
            )
    return rows


# =========================


# -----------------------------------------------------------------------------
# Weitere Jinja-Filter
# -----------------------------------------------------------------------------
@app.template_filter("chf")
def chf_filter(value):
    """Formatiert Zahlen als Schweizer Franken, z. B. CHF 9'000."""
    try:
        n = int(float(value))
        formatted = f"{n:,}".replace(",", "'")
        return f"CHF {formatted}"
    except Exception:
        return value


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html", active_page="home")


START_URL = None


@app.route("/submit", methods=["POST"])
def submit():
    global START_URL
    # Form-Felder (Namen müssen zu deinem index.html passen)
    produkt = request.form.get("produkt", "").strip()
    preis = request.form.get("preis", "").strip()
    region = request.form.get("region", "").strip()

    # START_URL = "https://www.ebay.ch/sch/119544/i.html?_nkw=gitarre&_from=R40&_ipg=240"

    # Import von Eingabe aus Fronted
    # Baut die Start-URL dynamisch mit dem Produktnamen

    BASE_URL = (
        "https://www.ebay.ch/sch/i.html?_nkw={}&_sacat=0&_from=R40&_trksid=m570.l1313"
    )
    START_URL = BASE_URL.format(produkt)

    print("Die URL ist:" + START_URL)
    print("Main-Funktion wurde ausgeführt")
    # Formular-Daten auslesen
    #  form_data = request.form  # <--- werkzeug.datastructures.ImmutableMultiDict

    # In ein normales Dictionary umwandeln
    #  data_dict = form_data.to_dict()

    # Optional: Werte umwandeln oder prüfen
    # data_dict["preis"] = int(data_dict["preis"]) if "preis" in data_dict else None

    # Übergabe an scraper.py
    # result = scrape_data(form_data)

    # print(data_dict)
    # Beispielausgabe: {'produkt': 'Apfel', 'preis': 2, 'region': 'Zürich'}

    # return jsonify({"empfangen": data_dict})

    # in CSV schreiben
    # append_row(produkt_url=produkt, preis=preis, region=region)

    # neuen Eintrag für einmalige Anzeige zwischenspeichern
    # session["new_row"] = {
    #    "produkt": produkt,
    #    "preis": preis,
    #    "region": region,
    #    "link": produkt,
    # }
    # return redirect(url_for("suchresultat_aktuell"))

    #  @app.route("/suchresultat/aktuell")
    #  def suchresultat_aktuell():
    """Zeigt nur den zuletzt gespeicherten Eintrag + Erfolgsmeldung."""
    #  new_row = session.pop("new_row", None)  # nur einmal anzeigen
    # if not new_row:
    #   return redirect(url_for("suchresultat_total"))
    # return render_template(
    #   "suchresultat_aktuell.html",
    #   daten=[new_row],
    #   message="1 neuer Eintrag wurde gespeichert.",
    #   success=True,
    #   active_page="results",
    #  )

    # @app.route("/suchresultat")
    # def suchresultat_total():
    """Alle gespeicherten Einträge anzeigen."""


#   daten = load_rows_for_table()
#   return render_template(
#     "suchresultat_total.html",
#     daten=daten,
#     active_page="results",
#  )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
#  if __name__ == "__main__":
#   app.run(debug=True)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Baut die Start-URL dynamisch mit dem Produktnamen
# BASE_URL = "https://www.ebay.ch/sch/i.html?_nkw={}&_from=R40&_ipg=240"
# START_URL = BASE_URL.format(produkt)

# =========================
# Selektoren zentral definieren
# =========================
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

# =========================
# Konfiguration
# =========================
# from app import produkt

# BASE_URL = (
# "https://www.ebay.ch/sch/i.html?_nkw={}&_sacat=0&_from=R40&_trksid=m570.l1313"
# )
# START_URL = BASE_URL.format(produkt)
OUT_CSV = "scraping_output.csv"
MAX_PAGES = 10
HEADLESS = False  # gilt nur für Chrome-Start; Safari ignoriert dieses Flag

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

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ebay_scraper")


# =========================
# Driver-Setup (OS-basiert)
# =========================
def setup_driver(headless: bool = HEADLESS) -> WebDriver:
    """
    Wählt den passenden WebDriver basierend auf os.name:
      - Windows (os.name == 'nt'): Chrome (webdriver.Chrome)
      - POSIX (os.name == 'posix'): Safari (webdriver.Safari)
    Liefert ein WebDriver-Objekt oder wirft eine Exception.
    """
    if os.name == "nt":
        logger.info("Betriebssystem erkannt: Windows (nt) -> Starte Chrome WebDriver")
        return _start_chrome(headless)
    elif os.name == "posix":
        logger.info("Betriebssystem erkannt: POSIX -> Starte Safari WebDriver")
        return _start_safari()
    else:
        msg = f"Unbekanntes Betriebssystem (os.name={os.name}). Unterstützt: 'nt' (Windows), 'posix' (macOS/Linux)."
        logger.error(msg)
        raise RuntimeError(msg)


def _start_chrome(headless: bool) -> WebDriver:
    """Initialisiert Chrome über webdriver-manager (Windows-Variante)."""
    # Chrome helper imports
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

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1280, 900)
        return driver
    except Exception as e:
        logger.exception("Fehler beim Starten des Chrome WebDrivers: %s", e)
        raise


def _start_safari() -> WebDriver:
    """Initialisiert Safari WebDriver (macOS)."""
    try:
        driver = webdriver.Safari()
        driver.set_window_size(1280, 900)
        return driver
    except Exception as e:
        logger.exception("Fehler beim Starten des Safari WebDrivers: %s", e)
        raise


# =========================
# Common helper functions (arbeiten mit generischem WebDriver)
# =========================
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
                    continue

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
        logger.debug("Fehler beim Akzeptieren des Cookie-Banners: %s", e)


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


# =========================
# Parsing-Helfer (inkl. Bild-Extraktion)
# =========================
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
    """
    Liefert die bestmögliche Bild-URL aus einem <img>-Element.
    Priorität: src -> data-src/data-img/data-srcset/data-lazy -> srcset.
    """
    if img_el is None:
        return ""
    # 1) src direkt (häufigste)
    src = img_el.get("src")
    if src:
        return src.strip()
    # 2) lazy-load Attribute
    for attr in ("data-src", "data-img", "data-srcset", "data-lazy"):
        val = img_el.get(attr)
        if val:
            return _parse_src_value(val)
    # 3) srcset-Fallback
    srcset = img_el.get("srcset")
    if srcset:
        return _parse_srcset_first(srcset)
    return ""


# =========================
# Kernparser (mit Filter für Promo + Dedupe)
# =========================
def parse_items_from_html(html: str, seen_links: set) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(ITEMS_SELECTOR)
    rows: List[Dict] = []

    logger.info("Karten gefunden (ITEMS_SELECTOR): %d", len(cards))

    for card in cards:
        title = _clean_title(_sel_text(card, TITLE_SELECTOR)).strip()
        if not title:
            continue

        low = title.lower()
        if any(bad in low for bad in BAD_TITLE_SUBSTRINGS):
            continue

        link = _sel_href(card, LINK_SELECTOR)
        if not link:
            continue

        if "/itm/" not in link:
            continue

        if link in seen_links:
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
                "image": image,  # neu: Bild-URL als letzte Spalte
            }
        )

    return rows


# =========================
# Scraper (mit Pagination)
# =========================
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
            with open("debug_page1.html", "w", encoding="utf-8") as f:
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


# =========================
# CSV Export
# =========================
def save_to_csv(items: List[Dict], filename: str = OUT_CSV) -> None:
    fieldnames = ["titel", "aktualitaet", "preis", "land", "versand", "link", "image"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(items)
    logger.info("CSV gespeichert: %s  (%d Zeilen)", filename, len(items))


# =========================
# main
# =========================
def main() -> None:
    driver = setup_driver()
    try:
        logger.info("Starte Scraping…")
        rows = scrape_all(driver, START_URL, max_pages=MAX_PAGES)
        if not rows:
            logger.warning("Es wurden keine Einträge extrahiert.")
        save_to_csv(rows, OUT_CSV)
    finally:
        try:
            driver.quit()
        except Exception:
            logger.debug("Fehler beim Schließen des WebDrivers (ignoriert).")
        logger.info("Fertig.")


if __name__ == "__main__":
    main()
    app.run(debug=True)
