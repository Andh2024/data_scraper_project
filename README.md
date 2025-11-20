# PriceHunter – Webbasierte Preisvergleichs-Applikation

**PriceHunter** ist eine Python-basierte Webapplikation, die es ermöglicht, Preise von Produkten auf Online-Marktplätzen (aktuell: eBay Schweiz) zu vergleichen.  
Die Applikation wurde im Rahmen des Moduls SWEN – Software Engineering im Studiengang Master of Science in Wirtschaftsinformatik entwickelt.

Ziel des Projekts war es, die Grundlagen von **Softwareentwicklung, Teamarbeit mit GitHub, Python-Backend-Entwicklung (Flask)** und **Web Scraping mit Selenium & BeautifulSoup** praktisch zu erlernen und anzuwenden.

---

## Funktionen und Zielsetzung

- **Produktsuche:** Nutzer:innen können ein Produkt und einen Maximalpreis eingeben.
- **Scraping:** Die Applikation ruft automatisiert eBay.ch auf und extrahiert Produktinformationen.
- **Datenbereinigung:** Rohdaten werden automatisch transformiert und in bereinigter Form gespeichert.
- **Darstellung:** Ergebnisse werden über ein Flask-Webinterface (Bootstrap-Design, Light-/Dark-Mode) angezeigt.
- **Datenspeicherung:** Eingaben, Rohdaten und bereinigte Daten werden lokal als CSV-Dateien gespeichert.

---

## Projektstruktur

PriceHunter/
│
├── main.py                         # Hauptapplikation (Flask + Scraper)
├── data_transformer_cleansing.py   # Datenbereinigung (CSV → CSV)
├── requirements.txt                # Projektabhängigkeiten
├── README.md                       # Projektdokumentation
│
├── templates/                      # HTML-Templates (Jinja2)
│ ├── base.html
│ ├── index.html
│ ├── suchresultat_aktuell.html
│ └── suchresultat_total.html
│
├── data.csv                        # Eingabe-Log (Produktsuche)
├── output_scraper.csv              # Rohdaten aus Web-Scraping
└── output_clean.csv                # Bereinigte Daten nach Data Cleansing

---

## Systemübersicht

Die Applikation besteht aus drei Hauptkomponenten:

| Komponente                     | Beschreibung                                                              |
| ------------------------------ | ------------------------------------------------------------------------- |
| **Frontend (Flask Templates)** | Benutzeroberfläche (Formular & Resultate) – basiert auf Bootstrap 5       |
| **Backend (Python Flask-App)** | Logik für Routing, Scraping (Selenium + BeautifulSoup), Datenverarbeitung |
| **Datenspeicherung**           | CSV-Dateien für Eingabe-Log, Rohdaten und bereinigte Daten                |

Das **Block-Diagramm** befindet sich im Jupyter Notebook --> **`PriceHunter_Block_Diagramm.ipynb`**

---

## Get started

### 1. Voraussetzungen

- Python 3.9 oder höher
- Google Chrome (aktuell) **oder** Safari mit aktivierter Option „Entferne Automation“
- Internetverbindung (für eBay-Scraping)

### 2. Installation der Abhängigkeiten

```bash
pip install -r requirements.txt

### 3. Start der Anwendung

python main.py

Die Web-App läuft lokal unter: http://127.0.0.1:5000/
```
