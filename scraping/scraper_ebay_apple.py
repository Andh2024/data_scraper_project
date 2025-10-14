import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup


def setup_driver():
    driver = webdriver.Safari()
    driver.set_window_size(1200, 800)
    return driver


def accept_cookies(driver):
    try:
        time.sleep(2)
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = btn.text.strip().lower()
            if (
                "alle akzeptieren" in text
                or "akzeptieren" in text
                or "accept all" in text
            ):
                btn.click()
                print("✅ Cookie-Banner akzeptiert.")
                time.sleep(1)
                return
    except Exception as e:
        print("⚠️ Fehler beim Akzeptieren des Cookie-Banners:", e)


def scrape_page(driver, url):
    driver.get(url)
    accept_cookies(driver)
    time.sleep(3)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    items = []
    # Hier ggf. den Selektor anpassen, falls dein Ziel nicht in `li.s-item` steckt
    cards = soup.select(".srp-river-main li.s-item, .srp-river-main li.s-card")
    for card in cards:
        # Debug-Ausgabe
        # print("processing card")
        # **Neues Feld: das, wonach du gefragt hast**
        span_default_tag = card.select_one(
            "div.s-card__title span.su-styled-text.primary.default"
        )
        span_default_text = (
            span_default_tag.get_text(strip=True) if span_default_tag else ""
        )
        # Beispiel zusätzliche Felder — du musst sie anpassen, je nach Seite
        # Hier nur als Platzhalter; du musst ggf. die Selektoren überprüfen
        price_tag = card.select_one("span.s-item__price")
        price_text = price_tag.get_text(strip=True) if price_tag else ""
        # Weitere Felder, falls vorhanden
        # span_secondary_default / span_secondary_large / span_italic_large etc.
        span_secondary_default = ""  # TODO: richtiger Selektor
        span_secondary_large = ""  # TODO: richtiger Selektor
        span_italic_large = ""  # TODO: richtiger Selektor
        items.append(
            {
                "imageDescription": "",  # optional: z. B. card.select_one("img")["alt"]
                "span_secondary_default": span_secondary_default,
                "span_secondary_large": span_secondary_large,
                "price": price_text,
                "span_italic_large": span_italic_large,
                # dein gewünschtes neues Feld:
                "span_default": span_default_text,
            }
        )
    return items


def save_to_csv(items, filename="reisegitarren.csv"):
    # Beachte: wir müssen hier das neue Feld "span_default" aufnehmen
    fieldnames = [
        "imageDescription",
        "span_secondary_default",
        "span_secondary_large",
        "price",
        "span_italic_large",
        "span_default",
    ]
    with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(item)


def main():
    url = "https://www.ebay.ch/sch/159948/i.html?_nkw=gitarre&_from=R40"
    driver = setup_driver()
    try:
        print("🔍 Starte Scraping…")
        items = scrape_page(driver, url)
        print(f"✅ {len(items)} Einträge gefunden.")
        save_to_csv(items)
        print("💾 Daten gespeichert in 'reisegitarren.csv'")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
