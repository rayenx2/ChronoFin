"""Shared pytest fixtures."""
import os
import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta

# Set env vars before any imports
os.environ.setdefault("ALPHA_VANTAGE_KEY",  "test_key")
os.environ.setdefault("POSTGRES_URL", "postgresql://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL",    "redis://localhost:6379")
os.environ.setdefault("MODEL_DIR",    "/tmp/test_models")
os.environ.setdefault("PROCESSED_PATH", "/tmp/test_processed")


@pytest.fixture
def sample_ohlcv_df():
    np.random.seed(42)
    n = 120
    dates  = pd.date_range(end=date.today(), periods=n, freq="B")
    prices = 185.0 * np.cumprod(1 + np.random.normal(0, 0.012, n))
    return pd.DataFrame({
        "symbol":         "AAPL",
        "date":           dates,
        "open":           prices * np.random.uniform(0.99, 1.00, n),
        "high":           prices * np.random.uniform(1.00, 1.01, n),
        "low":            prices * np.random.uniform(0.99, 1.00, n),
        "close":          prices,
        "adjusted_close": prices,
        "volume":         np.random.randint(10_000_000, 80_000_000, n).astype(int),
        "ingested_at":    pd.Timestamp.utcnow(),
        "day_of_week":    pd.to_datetime(dates).dayofweek,
        "vwap":           prices,
    })


@pytest.fixture
def processed_parquet(tmp_path, sample_ohlcv_df):
    from data_processing.feature_engineering import compute_indicators_pandas
    df = compute_indicators_pandas(sample_ohlcv_df)
    path = tmp_path / "processed.parquet"
    df.to_parquet(path)
    return str(path)
