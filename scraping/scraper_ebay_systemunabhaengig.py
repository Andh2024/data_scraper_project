import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1200,800")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Headless-Modus (ohne Fenster) optional aktivieren:
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36"
    )

    # Starte ChromeDriver (Pfad sollte durch Homebrew verfügbar sein)
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def accept_cookies(driver):
    """Akzeptiert das Cookie-Banner, falls sichtbar."""
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
    time.sleep(3)  # Warten, bis Seite geladen ist

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    items = []

    # Beispielhafte Karte: passe dies ggf. an die Struktur der Seite an
    cards = soup.select("li.s-item")

    for card in cards:
        # imageDescription (meist im alt-Attribut des <img>)
        img = card.find("img")
        image_description = img.get("alt", "").strip() if img else ""

        # span class="su-styled-text secondary default"
        span1 = card.find("span", class_="su-styled-text secondary default")
        span1_text = span1.get_text(strip=True) if span1 else ""

        # span class="su-styled-text secondary large"
        span2 = card.find("span", class_="su-styled-text secondary large")
        span2_text = span2.get_text(strip=True) if span2 else ""

        # Preis – Versuch über bekannte Preisstruktur
        price_span = card.find("span", class_="s-item__price")
        price_text = price_span.get_text(strip=True) if price_span else ""

        # span class="su-styled-text italic large"
        span3 = card.find("span", class_="su-styled-text italic large")
        span3_text = span3.get_text(strip=True) if span3 else ""

        items.append(
            {
                "imageDescription": image_description,
                "span_secondary_default": span1_text,
                "span_secondary_large": span2_text,
                "price": price_text,
                "span_italic_large": span3_text,
            }
        )

    return items


def save_to_csv(items, filename="reisegitarren.csv"):
    fieldnames = [
        "imageDescription",
        "span_secondary_default",
        "span_secondary_large",
        "price",
        "span_italic_large",
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
