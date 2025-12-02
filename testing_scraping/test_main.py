from main import *

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
    assert "10" in versand, f"Versandkosten nicht korrekt extrahiert: '{versand}'"


def test_extract_image_url_returns_valid_url():
    """Prüft, ob extract_image_url eine korrekte Bild-URL liefert."""
    html = '<img src="https://example.com/test.jpg" alt="demo">'
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    result = extract_image_url(img)
    assert result == "https://example.com/test.jpg"
