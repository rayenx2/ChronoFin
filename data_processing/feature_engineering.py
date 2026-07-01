"""
Technical indicator computation using Pandas UDFs for per-symbol parallelism.
Computes RSI, MACD, Bollinger Bands, ATR, and return features.
"""
import pandas as pd
import numpy as np
import ta
from loguru import logger

try:
    from pyspark.sql import DataFrame, SparkSession
    from pyspark.sql.types import StructField, DoubleType
    _PYSPARK_AVAILABLE = True
except ImportError:
    _PYSPARK_AVAILABLE = False
    DataFrame = None  # type: ignore[assignment,misc]
    SparkSession = None  # type: ignore[assignment]


def _compute_indicators(pdf: pd.DataFrame) -> pd.DataFrame:
    """Applied per-symbol group inside a Pandas UDF."""
    pdf = pdf.sort_values("date").copy()
    close = pdf["close"]
    high  = pdf["high"]
    low   = pdf["low"]

    # RSI-14
    pdf["rsi_14"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd_obj = ta.trend.MACD(close)
    pdf["macd"]        = macd_obj.macd()
    pdf["macd_signal"] = macd_obj.macd_signal()
    pdf["macd_hist"]   = macd_obj.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    pdf["bb_upper"] = bb.bollinger_hband()
    pdf["bb_lower"] = bb.bollinger_lband()
    pdf["bb_width"] = bb.bollinger_wband()

    # ATR
    pdf["atr_14"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    # Returns
    pdf["return_1d"] = close.pct_change(1)
    pdf["return_5d"] = close.pct_change(5)

    return pdf


def add_technical_indicators(df, spark=None):
    """Apply technical indicators via Pandas UDF grouped by symbol (Spark) or pandas fallback."""
    if not _PYSPARK_AVAILABLE or spark is None:
        return compute_indicators_pandas(df)

    logger.info("Computing technical indicators via Pandas UDF...")
    from pyspark.sql.types import StructField, DoubleType  # noqa: F811
    output_schema = df.schema
    for field_name in [
        "rsi_14", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_lower", "bb_width",
        "atr_14", "return_1d", "return_5d",
    ]:
        output_schema = output_schema.add(StructField(field_name, DoubleType(), True))

    return df.groupby("symbol").applyInPandas(_compute_indicators, schema=output_schema)


def compute_indicators_pandas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pure-Pandas version for use outside Spark (single-symbol inference).
    df must have: date, open, high, low, close, volume columns, sorted ascending.
    """
    df = df.sort_values("date").copy()
    result_frames = []
    for symbol, group in df.groupby("symbol"):
        result_frames.append(_compute_indicators(group))
    return pd.concat(result_frames).reset_index(drop=True)
