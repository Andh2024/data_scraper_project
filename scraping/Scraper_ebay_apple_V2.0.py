import time
import csv
from typing import List, Dict, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from bs4 import BeautifulSoup

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
NEXT_SELECTOR = ".pagination__next, a[rel='next'], a[aria-label='Weiter']"

# =========================
# Konfiguration
# =========================
START_URL = "https://www.ebay.ch/sch/119544/i.html?_nkw=gitarre&_from=R40&_ipg=240"
OUT_CSV = "scraping_output.csv"
MAX_PAGES = 10

TITLE_BAD_PHRASES = [
    "wird in neuem fenster oder tab geöffnet",
    "wird in neuem fenster geöffnet",
    "wird in einem neuen fenster oder tab geöffnet",
    "öffnet sich in einem neuen fenster oder tab",
    "opens in a new window or tab",
    "open in a new window or tab",
]

# Titel, die grundsätzlich übersprungen werden (Promo/Ads/Shop-Tiles)
BAD_TITLE_SUBSTRINGS = [
    "shop on ebay",
    "shoppen auf ebay",
    "gesponsert",
    "sponsored",
    "anzeige",
    "advertisement",
    "ad:",
]


# =========================
# Selenium Setup (Safari)
# =========================
def setup_driver() -> webdriver.Safari:
    driver = webdriver.Safari()
    driver.set_window_size(1280, 900)
    return driver


def accept_cookies(driver: webdriver.Safari) -> None:
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
                    print("✅ Cookie-Banner akzeptiert.")
                    time.sleep(0.8)
                    return
                except WebDriverException:
                    pass
        for f in driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                driver.switch_to.frame(f)
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
                        btn.click()
                        print("✅ Cookie-Banner (iframe) akzeptiert.")
                        time.sleep(0.8)
                        driver.switch_to.default_content()
                        return
                driver.switch_to.default_content()
            except WebDriverException:
                driver.switch_to.default_content()
    except Exception as e:
        print("⚠️ Fehler beim Akzeptieren des Cookie-Banners:", e)


def wait_for_results(driver: webdriver.Safari, timeout: int = 25) -> None:
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, RESULTS_CONTAINER_SELECTOR))
    )


def lazy_scroll(driver: webdriver.Safari, steps: int = 6, pause: float = 0.8) -> None:
    last_h = 0
    for _ in range(steps):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        h = driver.execute_script("return document.body.scrollHeight;")
        if h == last_h:
            break
        last_h = h


# =========================
# Parsing-Helfer
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


# =========================
# Kernparser (mit Filter für Promo + Dedupe)
# =========================
def parse_items_from_html(html: str, seen_links: set) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(ITEMS_SELECTOR)
    rows: List[Dict] = []

    print(f"🔎 Karten gefunden (ITEMS_SELECTOR): {len(cards)}")

    for card in cards:
        title = _clean_title(_sel_text(card, TITLE_SELECTOR)).strip()
        if not title:
            continue

        # 1) Promo-/Teaser-/Ad-Karten nach Titel ausschließen
        low = title.lower()
        if any(bad in low for bad in BAD_TITLE_SUBSTRINGS):
            continue

        link = _sel_href(card, LINK_SELECTOR)
        if not link:
            continue

        # 2) Nur echte Artikelseiten akzeptieren
        if "/itm/" not in link:
            continue

        # 3) Deduplizieren (seitenübergreifend)
        if link in seen_links:
            continue
        seen_links.add(link)

        price = _sel_text(card, PRICE_SELECTOR)
        condition = _sel_text(card, CONDITION_SELECTOR)
        land, versand = _extract_location_and_shipping(card)

        rows.append(
            {
                "titel": title,
                "aktualitaet": condition,
                "preis": price,
                "land": land,
                "versand": versand,
                "link": link,
            }
        )

    return rows


# =========================
# Scraper (mit Pagination)
# =========================
def scrape_all(
    driver: webdriver.Safari, start_url: str, max_pages: int = MAX_PAGES
) -> List[Dict]:
    all_rows: List[Dict] = []
    current_url = start_url
    seen_links: set = set()  # globales Set für Dedupe über alle Seiten

    for page in range(1, max_pages + 1):
        print(f"\n➡️  Lade Seite {page}: {current_url}")
        driver.get(current_url)
        accept_cookies(driver)

        try:
            wait_for_results(driver, timeout=25)
        except TimeoutException:
            print("⏳ Trefferliste nicht rechtzeitig erschienen – parse trotzdem …")

        lazy_scroll(driver, steps=6, pause=0.8)
        html = driver.page_source

        if page == 1:
            with open("debug_page1.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("🧩 Debug gespeichert: debug_page1.html")

        page_rows = parse_items_from_html(html, seen_links)
        print(f"   → {len(page_rows)} verwertbare Angebote (nach Filter)")
        if not page_rows and page == 1:
            print("⚠️  Keine Angebote geparst. Prüfe debug_page1.html und Selektoren.")
        all_rows.extend(page_rows)

        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one(NEXT_SELECTOR)
        if not next_link or not next_link.get("href"):
            print("ℹ️  Keine weitere Seite gefunden.")
            break
        current_url = next_link["href"]
        time.sleep(1.1)

    return all_rows


# =========================
# CSV Export
# =========================
def save_to_csv(items: List[Dict], filename: str = OUT_CSV) -> None:
    fieldnames = ["titel", "aktualitaet", "preis", "land", "versand", "link"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(items)
    print(f"💾 CSV gespeichert: {filename}  ({len(items)} Zeilen)")


# =========================
# main
# =========================
def main():
    driver = setup_driver()
    try:
        print("🔍 Starte Scraping…")
        rows = scrape_all(driver, START_URL, max_pages=MAX_PAGES)
        if not rows:
            print("❌ Es wurden keine Einträge extrahiert.")
        save_to_csv(rows, OUT_CSV)
    finally:
        driver.quit()
        print("✅ Fertig.")


if __name__ == "__main__":
    main()
