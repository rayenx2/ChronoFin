"""Integration tests for the FastAPI layer."""
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


MOCK_PREDICTION = {
    "symbol": "AAPL",
    "current_price": 185.0,
    "predicted_price": 186.5,
    "confidence_lower": 182.0,
    "confidence_upper": 191.0,
    "confidence_score": 0.82,
    "prediction_date": "2024-01-16",
    "model_version": "v1.0",
    "sentiment_score": 0.15,
    "sentiment_label": "Positive",
    "model_trained_at": "2024-01-14",
}

MOCK_MARKET_DATA = {
    "symbol": "AAPL",
    "days": 30,
    "count": 2,
    "data": [
        {"date": "2024-01-14", "open": 183.0, "high": 185.5,
         "low": 182.0, "close": 184.5, "volume": 55000000,
         "rsi_14": 62.5, "macd": 1.2, "macd_signal": 0.9,
         "bb_upper": 190.0, "bb_lower": 178.0},
        {"date": "2024-01-15", "open": 184.5, "high": 186.0,
         "low": 183.5, "close": 185.0, "volume": 48000000,
         "rsi_14": 63.1, "macd": 1.3, "macd_signal": 1.0,
         "bb_upper": 190.5, "bb_lower": 178.5},
    ],
}


@pytest.fixture
def client():
    with patch("data_storage.cache.get_client") as mock_redis:
        mock_redis.return_value.ping.return_value = True
        mock_redis.return_value.get.return_value = None
        mock_redis.return_value.setex.return_value = True
        from api.main import app
        yield TestClient(app)


# ── Health endpoint ───────────────────────────────────────────────────────────

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Predictions endpoint ──────────────────────────────────────────────────────

def test_get_prediction_success(client):
    with patch("api.routers.predictions.get_cached_prediction", return_value=None), \
         patch("api.routers.predictions.predict_next_day", return_value=MOCK_PREDICTION):
        response = client.get("/api/v1/predictions/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["predicted_price"] == 186.5
    assert 0 <= data["confidence_score"] <= 1


def test_get_prediction_cached(client):
    with patch("api.routers.predictions.get_cached_prediction", return_value=MOCK_PREDICTION):
        response = client.get("/api/v1/predictions/AAPL")
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"


def test_get_prediction_symbol_uppercased(client):
    with patch("api.routers.predictions.get_cached_prediction", return_value=None), \
         patch("api.routers.predictions.predict_next_day", return_value=MOCK_PREDICTION):
        response = client.get("/api/v1/predictions/aapl")
    assert response.status_code == 200


def test_get_prediction_model_not_found(client):
    with patch("api.routers.predictions.get_cached_prediction", return_value=None), \
         patch("api.routers.predictions.predict_next_day",
               side_effect=FileNotFoundError("no model")):
        response = client.get("/api/v1/predictions/AAPL")
    assert response.status_code == 404


def test_batch_predictions(client):
    with patch("api.routers.predictions.get_cached_prediction", return_value=None), \
         patch("api.routers.predictions.predict_next_day", return_value=MOCK_PREDICTION):
        response = client.get("/api/v1/predictions/?symbols=AAPL,MSFT")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── Market data endpoint ──────────────────────────────────────────────────────

def test_get_market_data_success(client):
    with patch("api.routers.market_data.read_prices") as mock_read:
        import pandas as pd
        mock_read.return_value = pd.DataFrame(MOCK_MARKET_DATA["data"])
        response = client.get("/api/v1/market/AAPL?days=30")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert "data" in data


def test_get_market_data_invalid_symbol(client):
    response = client.get("/api/v1/market/INVALID")
    assert response.status_code == 404


def test_get_market_data_days_validation(client):
    response = client.get("/api/v1/market/AAPL?days=0")
    assert response.status_code == 422  # Pydantic validation error

    response = client.get("/api/v1/market/AAPL?days=999")
    assert response.status_code == 422


# ── Response schema validation ────────────────────────────────────────────────

def test_prediction_response_has_required_fields(client):
    with patch("api.routers.predictions.get_cached_prediction", return_value=None), \
         patch("api.routers.predictions.predict_next_day", return_value=MOCK_PREDICTION):
        response = client.get("/api/v1/predictions/AAPL")

    required = {"symbol", "current_price", "predicted_price",
                "confidence_lower", "confidence_upper",
                "confidence_score", "prediction_date", "model_version"}
    assert required.issubset(response.json().keys())
