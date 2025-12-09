import pytest
from unittest.mock import patch
from main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.mark.parametrize(
    "produkt_begriff",
    [
        "Ski",
        "Ski Schuhe",
        "Skischuhe",
        "Skistöcke",
        "Ski Stöcke",
    ],
)
@patch("main.run_scrape")  # run_scrape wird ersetzt
def test_submit_redirects_and_calls_scraper_with_correct_kwargs(
    mock_run_scrape, client, produkt_begriff
):
    # Mock-Rückgabe → kein realer Scraper läuft
    mock_run_scrape.return_value = []

    response = client.post(
        "/submit",
        data={"produkt": produkt_begriff, "preis": "999", "region": "CH"},
    )

    # 1) Route macht Redirect → 302
    assert response.status_code == 302

    # 2) Ziel-URL prüfen
    redirect_location = response.headers.get("Location", "")
    assert "/suchresultat/aktuell" in redirect_location

    # 3) Scraper wurde genau 1x aufgerufen
    mock_run_scrape.assert_called_once()

    # 4) Prüfen, ob die Keyword-Argumente korrekt übergeben wurden
    args, kwargs = mock_run_scrape.call_args

    # Es MUSS ein keyword argument 'query' geben
    assert kwargs["query"] == produkt_begriff

    # Preis prüfen → immer "999" aus dem Test
    assert kwargs["preis"] == "999"
