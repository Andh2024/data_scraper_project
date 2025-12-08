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


def test_extract_location_and_shipping_returns_correct_values():
    """Testet, ob Land und Versandkosten korrekt erkannt werden."""
    html = """
    <div>
        <span class="s-item__location">aus Schweiz</span>
        <span class="s-item__shipping">+ CHF 10 Versand</span>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    land, versand = extract_location_and_shipping(soup)
    assert "Schweiz" in land
    assert "10" in versand


def test_extract_image_url_returns_valid_url():
    """Prüft, ob extract_image_url eine korrekte Bild-URL liefert."""
    html = '<img src="https://example.com/test.jpg" alt="demo">'
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    result = extract_image_url(img)
    assert result == "https://example.com/test.jpg"


def test_parse_items_from_html_verhindert_duplikate_mit_seen_links():
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


def test_save_to_csv_schreibt_header_und_zeilen(tmp_path):
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


def test_append_row_schreibt_zeile_in_csv(tmp_path, monkeypatch):
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


# ---------- Fake Selenium-Objekte ----------


class FakeButton:
    def __init__(self, text):
        self.text = text
        self.clicked = False

    def click(self):
        self.clicked = True


class FakeDriver:
    def __init__(self, buttons=None):
        self._buttons = buttons or []
        # einfache Attr, damit accept_cookies driver.switch_to.default_content() aufrufen könnte,
        # falls wir später iframes testen wollen
        self.switch_to = self

    def find_elements(self, by=None, value=None):
        # accept_cookies ruft:
        #   find_elements(By.TAG_NAME, "button")
        #   find_elements(By.TAG_NAME, "iframe")
        if value == "button":
            return self._buttons
        if value == "iframe":
            return []  # für diesen Test: keine iframes
        return []

    # Platzhalter, falls accept_cookies mal frame()/default_content() aufruft
    def frame(self, frame):
        pass

    def default_content(self):
        pass


# ---------- Eigentlicher Test ----------


def test_accept_cookies_clicks_main_button(monkeypatch):
    # Wir bauen einen Fake-Button mit dem Text, den dein Code sucht
    btn = FakeButton("Alle akzeptieren")

    # FakeDriver mit genau diesem Button
    driver = FakeDriver(buttons=[btn])

    # time.sleep patchen, damit der Test nicht wirklich wartet
    monkeypatch.setattr(time, "sleep", lambda x: None)

    # Aufruf der echten Funktion aus main.py
    accept_cookies(driver)

    # Erwartung: der Button wurde angeklickt
    assert btn.clicked is True


def test_url_building():
    url = BASE_URL.format("LED Stehlampe", "200")
    assert (
        url
        == "https://www.ebay.ch/sch/i.html?_nkw=LED&Stehlampe&_sacat=0&_from=R40&_trksid=m570.l1313&_udhi=200"
    )
