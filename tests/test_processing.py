"""Unit tests for data processing layer."""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta


def make_sample_df(symbol: str = "AAPL", n: int = 100) -> pd.DataFrame:
    dates = pd.date_range(end=date.today(), periods=n, freq="B")
    base = 185.0
    prices = base * np.cumprod(1 + np.random.normal(0, 0.01, n))
    return pd.DataFrame({
        "symbol": symbol,
        "date": dates,
        "open":           prices * np.random.uniform(0.99, 1.0, n),
        "high":           prices * np.random.uniform(1.0, 1.01, n),
        "low":            prices * np.random.uniform(0.99, 1.0, n),
        "close":          prices,
        "adjusted_close": prices,
        "volume":         np.random.randint(1_000_000, 80_000_000, n).astype(int),
        "ingested_at":    pd.Timestamp.utcnow(),
    })


# ── Feature engineering ───────────────────────────────────────────────────────

def test_compute_indicators_adds_rsi():
    from data_processing.feature_engineering import _compute_indicators
    df = make_sample_df(n=80)
    result = _compute_indicators(df)
    assert "rsi_14" in result.columns
    valid_rsi = result["rsi_14"].dropna()
    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()


def test_compute_indicators_adds_macd():
    from data_processing.feature_engineering import _compute_indicators
    df = make_sample_df(n=80)
    result = _compute_indicators(df)
    assert "macd" in result.columns
    assert "macd_signal" in result.columns
    assert "macd_hist" in result.columns


def test_compute_indicators_adds_bollinger():
    from data_processing.feature_engineering import _compute_indicators
    df = make_sample_df(n=80)
    result = _compute_indicators(df)
    assert "bb_upper" in result.columns
    assert "bb_lower" in result.columns
    non_null = result.dropna(subset=["bb_upper", "bb_lower"])
    assert (non_null["bb_upper"] >= non_null["bb_lower"]).all()


def test_compute_indicators_returns_correct_length():
    from data_processing.feature_engineering import _compute_indicators
    df = make_sample_df(n=60)
    result = _compute_indicators(df)
    assert len(result) == len(df)


def test_compute_indicators_returns_1d_returns():
    from data_processing.feature_engineering import _compute_indicators
    df = make_sample_df(n=60)
    result = _compute_indicators(df)
    assert "return_1d" in result.columns
    # 1-day return should be small for normal price series
    valid = result["return_1d"].dropna()
    assert (valid.abs() < 0.5).all()


# ── Data validator ────────────────────────────────────────────────────────────

def test_fallback_validator_passes_clean_data(tmp_path):
    df = make_sample_df(n=50)
    df["rsi_14"] = 55.0
    parquet_file = tmp_path / "data.parquet"
    df.to_parquet(parquet_file)

    from data_processing.data_validator import _run_fallback_suite
    assert _run_fallback_suite(str(parquet_file)) is True


def test_fallback_validator_fails_on_null_close(tmp_path):
    df = make_sample_df(n=50)
    df.loc[0, "close"] = None
    parquet_file = tmp_path / "data.parquet"
    df.to_parquet(parquet_file)

    from data_processing.data_validator import _run_fallback_suite
    assert _run_fallback_suite(str(parquet_file)) is False


def test_fallback_validator_fails_on_negative_price(tmp_path):
    df = make_sample_df(n=50)
    df.loc[0, "close"] = -5.0
    parquet_file = tmp_path / "data.parquet"
    df.to_parquet(parquet_file)

    from data_processing.data_validator import _run_fallback_suite
    assert _run_fallback_suite(str(parquet_file)) is False


def test_fallback_validator_fails_on_duplicates(tmp_path):
    df = make_sample_df(n=50)
    df = pd.concat([df, df.iloc[:1]], ignore_index=True)
    parquet_file = tmp_path / "data.parquet"
    df.to_parquet(parquet_file)

    from data_processing.data_validator import _run_fallback_suite
    assert _run_fallback_suite(str(parquet_file)) is False


# ── Schema validation ─────────────────────────────────────────────────────────

def test_stock_price_schema_valid():
    from data_processing.schema import StockPrice
    sp = StockPrice(
        symbol="aapl",  # should be uppercased
        date=date.today(),
        open=183.0, high=185.5, low=182.0, close=184.5,
        adjusted_close=184.5, volume=55_000_000,
    )
    assert sp.symbol == "AAPL"


def test_stock_price_schema_rejects_zero_price():
    from data_processing.schema import StockPrice
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        StockPrice(
            symbol="AAPL", date=date.today(),
            open=0.0, high=0.0, low=0.0, close=0.0,
            adjusted_close=0.0, volume=100,
        )


def test_stock_tick_schema_valid():
    from data_processing.schema import StockTick
    from datetime import datetime
    tick = StockTick(
        symbol="MSFT", price=375.0, volume=10000,
        bid=374.95, ask=375.05,
        timestamp=datetime.utcnow(), source="kafka",
    )
    assert tick.symbol == "MSFT"
    assert tick.bid < tick.ask
