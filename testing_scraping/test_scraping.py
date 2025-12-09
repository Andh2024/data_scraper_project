from main import *
import main

# test_scraper_functions.py
# Testet die zentralen Scraping-Hilfsfunktionen aus main.py

from bs4 import BeautifulSoup
from main import clean_title, extract_location_and_shipping, extract_image_url


def test_clean_title_removes_bad_phrases():
    """Testet, ob clean_title störende eBay-Zusätze entfernt."""
    input_title = "MacBook Pro – wird in neuem Fenster oder Tab geöffnet"
    result = clean_title(input_title)
    assert "wird in neuem" not in result
    assert result.startswith("MacBook Pro")


def test_extract_location_and_shipping():
    html = """
    <div>
        <div class="s-card__attribute-row">
            <span class="su-styled-text secondary large">+CHF 3.47 Versand</span>
        </div>
        <div class="s-card__attribute-row">
            <span class="su-styled-text secondary large">aus Deutschland</span>
        </div>
    </div>
    """

    soup = BeautifulSoup(html, "html.parser")

    land, versand = extract_location_and_shipping(soup)

    assert land == "aus Deutschland"
    assert "+CHF 3.47 Versand" in versand


def test_extract_image_url_returns_valid_url():
    """Prüft, ob extract_image_url eine korrekte Bild-URL liefert."""
    html = '<img src="https://example.com/test.jpg" alt="demo">'
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    result = extract_image_url(img)
    assert result == "https://example.com/test.jpg"


def test_parse_items_from_html_check_duplicates_marked_as_seen_links():
    """Prüft, ob Objekte mit gleichem Item-Link zur einmals geladen wird"""
    html = """
    <ul class="srp-results">
      <li class="s-item">
        <a class="s-item__link" href="https://www.ebay.ch/itm/123">
          <h3 class="s-item__title">Produkt 1</h3>
        </a>
        <span class="s-item__price">CHF 10.00</span>
      </li>
      <li class="s-item">
        <a class="s-item__link" href="https://www.ebay.ch/itm/123">
          <h3 class="s-item__title">Produkt 1 (Duplikat)</h3>
        </a>
        <span class="s-item__price">CHF 10.00</span>
      </li>
       <li class="s-item">
        <a class="s-item__link" href="https://www.ebay.ch/itm/123">
          <h3 class="s-item__title">Produkt 1 (Duplikat)</h3>
        </a>
        <span class="s-item__price">CHF 10.00</span>
      </li>
    </ul>
    """
    seen = set()
    rows = parse_items_from_html(html, seen)
    assert len(rows) == 1
    assert rows[0]["link"] == "https://www.ebay.ch/itm/123"
    assert "https://www.ebay.ch/itm/123" in seen


def test_save_to_csv_writes_header_and_lines(tmp_path):
    """Testet, ob Header und Daten korrekt im CSV zusammengebaut werden."""
    items = [
        {
            "titel": "A",
            "aktualitaet": "Neu",
            "preis": "CHF 1.00",
            "land": "aus Schweiz",
            "versand": "Gratis",
            "link": "https://example.com/a",
            "image": "https://example.com/a.jpg",
        },
        {
            "titel": "B",
            "aktualitaet": "Gebraucht",
            "preis": "CHF 2.00",
            "land": "aus Deutschland",
            "versand": "+ CHF 5.00 Versand",
            "link": "https://example.com/b",
            "image": "https://example.com/b.jpg",
        },
    ]

    filename = tmp_path / "test_output.csv"
    save_to_csv(items, filename)

    assert filename.exists()
    content = filename.read_text(encoding="utf-8")
    # Header-Felder
    for col in CSV_DATA_FIELDS:
        assert col in content
    # Daten
    assert "A" in content
    assert "B" in content


def test_append_row_writes_line_in_csv(tmp_path, monkeypatch):
    """Testet, ob die Formulareingabe je-weils als neue Zeile in der Datei «data.csv» gespeichert wird."""
    # CSV_PATH im Modul auf temporäre Datei umbiegen
    test_csv = tmp_path / "input_log.csv"
    monkeypatch.setattr(main, "CSV_PATH", test_csv)

    append_row(produkt_url="iphone", preis="100", region="Schweiz")

    assert test_csv.exists()
    lines = test_csv.read_text(encoding="utf-8").splitlines()
    # 1: Header, 2: Datenzeile
    assert len(lines) == 2
    assert "iphone" in lines[1]
    assert "100" in lines[1]
    assert "Schweiz" in lines[1]


def test_url_building():
    """Testet, ob die URL korrekt zusammengebaut wird."""
    query = "LED Stehlampe"
    preis_clean = "200"

    # Das erwartete Encoding des Suchbegriffs
    query_encoded = encode_query_limit_5(query)  # → "LED+Stehlampe"

    url = BASE_URL.format(query_encoded, preis_clean)

    assert (
        url
        == "https://www.ebay.ch/sch/i.html?_nkw=LED+Stehlampe&_sacat=0&_from=R40&_trksid=m570.l1313&_udhi=200"
    )


def test_url_building_limit_to_five_words():
    """Testet, ob maximal 5 Suchbegriffe in der URL verwendet werden."""
    query = "LED Stehlampe Wohnzimmer dimmbar grün hell"  # 6 Wörter
    preis_clean = "200"

    query_encoded = encode_query_limit_5(query)

    url = BASE_URL.format(query_encoded, preis_clean)

    assert (
        url
        == "https://www.ebay.ch/sch/i.html?_nkw=LED+Stehlampe+Wohnzimmer+dimmbar+gr%C3%BCn&_sacat=0&_from=R40&_trksid=m570.l1313&_udhi=200"
    )


def test_accept_cookies():
    """Testet, ob die Funktion accept_cookies ohne Fehler ausgeführt wird."""
    from main import accept_cookies
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    # Headless-Browser für den Test
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(
            "https://www.ebay.ch/sch/i.html?_nkw=k%C3%A4nguru&_sacat=0&_from=R40&_trksid=p4432023.m570.l1313"
        )  # Beispiel-URL
        accept_cookies(driver)
    finally:
        driver.quit()


def test_pagination_two_pages():
    """Testet, ob das Blättern funktioniert."""
    html_page_1 = """
        <html>
            <a class="pagination__next" href="http://example.com/page2">Weiter</a>
        </html>
    """

    html_page_2 = """
        <html>
            <a class="pagination__next" href="http://example.com/page3">Weiter</a>
        </html>
    """

    html_page_3 = """
        <html>
            <!-- keine weitere Seite -->
        </html>
    """

    # Seite 1 → Seite 2
    soup1 = BeautifulSoup(html_page_1, "html.parser")
    next1 = soup1.select_one(NEXT_SELECTOR)
    assert next1["href"] == "http://example.com/page2"

    # Seite 2 → Seite 3
    soup2 = BeautifulSoup(html_page_2, "html.parser")
    next2 = soup2.select_one(NEXT_SELECTOR)
    assert next2["href"] == "http://example.com/page3"

    # Seite 3 → keine weitere Seite
    soup3 = BeautifulSoup(html_page_3, "html.parser")
    next3 = soup3.select_one(NEXT_SELECTOR)
    assert next3 is None
