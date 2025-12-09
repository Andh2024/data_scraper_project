import pytest
from unittest.mock import patch
from main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@patch("main.run_scrape")  # run_scrape in main.py wird gemockt
def test_submit_post_redirects_correctly(mock_run_scrape, client):
    # Mock-Rückgabe für den Scraper (damit nichts Echt ausgeführt wird)
    mock_run_scrape.return_value = []

    # POST auf /submit
    response = client.post(
        "/submit", data={"produkt": "iPhone", "preis": "999", "region": "CH"}
    )

    # 1) Route sollte redirecten → Statuscode = 302
    assert response.status_code == 302

    # 2) Redirect-Ziel prüfen
    redirect_location = response.headers.get("Location", "")
    assert "/suchresultat/aktuell" in redirect_location

    # 3) Sicherstellen, dass run_scrape genau 1× aufgerufen wurde
    mock_run_scrape.assert_called_once()
