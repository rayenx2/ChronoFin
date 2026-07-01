"""Unit tests for data ingestion layer."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime


# ── AlphaVantageIngester ───────────────────────────────────────────────────────

MOCK_AV_RESPONSE = {
    "Time Series (Daily)": {
        "2024-01-15": {
            "1. open": "183.00",
            "2. high": "185.50",
            "3. low": "182.00",
            "4. close": "184.50",
            "5. adjusted close": "184.50",
            "6. volume": "55000000",
        },
        "2024-01-16": {
            "1. open": "184.50",
            "2. high": "186.00",
            "3. low": "183.50",
            "4. close": "185.00",
            "5. adjusted close": "185.00",
            "6. volume": "48000000",
        },
    }
}


@patch("data_ingestion.api_ingestion.requests.Session.get")
def test_ingest_symbol_returns_dataframe(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_AV_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    from data_ingestion.api_ingestion import AlphaVantageIngester
    ingester = AlphaVantageIngester(api_key="test_key")

    with patch("data_ingestion.api_ingestion.write_to_lake"):
        df = ingester.ingest_symbol("AAPL")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "symbol" in df.columns
    assert "close" in df.columns
    assert (df["symbol"] == "AAPL").all()


@patch("data_ingestion.api_ingestion.requests.Session.get")
def test_ingest_symbol_sorted_ascending(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_AV_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    from data_ingestion.api_ingestion import AlphaVantageIngester
    ingester = AlphaVantageIngester(api_key="test_key")
    df = ingester.ingest_symbol("AAPL")
    assert df["date"].is_monotonic_increasing


@patch("data_ingestion.api_ingestion.requests.Session.get")
def test_ingest_rate_limit_raises(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Note": "API rate limit reached"}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    from data_ingestion.api_ingestion import AlphaVantageIngester
    from tenacity import RetryError
    ingester = AlphaVantageIngester(api_key="test_key")

    with patch("time.sleep"):  # Skip actual sleep
        with pytest.raises(Exception):
            ingester.ingest_symbol("AAPL")


# ── Kafka producer ────────────────────────────────────────────────────────────

def test_simulate_tick_returns_valid_structure():
    from data_ingestion.kafka_producer import StockStreamProducer
    with patch("data_ingestion.kafka_producer.KafkaProducer"):
        producer = StockStreamProducer()
        tick = producer._simulate_tick("AAPL", 185.0)

    required_keys = {"symbol", "price", "volume", "bid", "ask", "timestamp", "source"}
    assert required_keys.issubset(tick.keys())
    assert tick["symbol"] == "AAPL"
    assert tick["price"] > 0
    assert tick["bid"] < tick["ask"]


def test_simulate_tick_price_drift():
    from data_ingestion.kafka_producer import StockStreamProducer
    with patch("data_ingestion.kafka_producer.KafkaProducer"):
        producer = StockStreamProducer()
    prices = [producer._simulate_tick("AAPL", 185.0)["price"] for _ in range(100)]
    # All prices should stay within ±30% of base (random walk sanity check)
    assert all(100 < p < 300 for p in prices)


# ── News ingestion ────────────────────────────────────────────────────────────

@patch("data_ingestion.news_ingestion.feedparser.parse")
def test_news_ingester_parses_feed(mock_parse):
    from types import SimpleNamespace
    from datetime import datetime
    now = datetime.utcnow()
    mock_parse.return_value = SimpleNamespace(
        entries=[
            SimpleNamespace(
                title="Apple hits all-time high",
                summary="AAPL surges on strong earnings",
                link="https://example.com/news/1",
                published_parsed=(now.year, now.month, now.day, now.hour, now.minute, 0, 0, 0, 0),
            )
        ],
        feed={"title": "Yahoo Finance"},
    )

    from data_ingestion.news_ingestion import NewsIngester
    ingester = NewsIngester(lookback_days=7)
    records = ingester._parse_feed("AAPL", "https://fake.rss.url")

    assert len(records) == 1
    assert records[0]["symbol"] == "AAPL"
    assert "Apple" in records[0]["headline"]
