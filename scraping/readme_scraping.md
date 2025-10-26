Befehl, um den Scraper laufen zu lassen:
-- für Windows: python ebay_reisegitarren_scraper.py
-- für Apple: play

1. Windows-Scraper
Ergebnis: CSV mit Spalten: id, title, price, link
Wesentliche Merkmale:
- Selenium + webdriver-manager (automatischer Chromedriver)
- Cookie-Banner-Erkennung und -Schließung
- Robuste, mehrstufige Selector-Fallbacks
- Debug-Ausgaben: debug_page.html, debug_first_item.html
- Extraktion der eBay-Item-ID aus Artikel-URLs
- Kompatibel mit Python 3.12