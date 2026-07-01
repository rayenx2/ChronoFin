"""Market data router — live OHLCV from Yahoo Finance with technical indicators."""
from datetime import date, timedelta
import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas import MarketDataResponse, OHLCVBar

try:
    from data_storage.warehouse import read_prices
except Exception:
    read_prices = None  # type: ignore[assignment]

router = APIRouter()

VALID_SYMBOLS = {
    "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "NVDA",
    "BTC-USD", "ETH-USD", "EURUSD=X",
}


def _fetch_yfinance(symbol: str, days: int) -> pd.DataFrame:
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=f"{days + 10}d", interval="1d")
    if df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"stock splits": "stock_splits"})
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    df = df[["date", "open", "high", "low", "close", "volume"]].tail(days)
    return df


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    try:
        import ta
        close = df["close"]
        high = df["high"]
        low = df["low"]
        df["rsi_14"] = ta.momentum.RSIIndicator(close, window=14).rsi().round(2)
        macd_obj = ta.trend.MACD(close)
        df["macd"] = macd_obj.macd().round(4)
        df["macd_signal"] = macd_obj.macd_signal().round(4)
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        df["bb_upper"] = bb.bollinger_hband().round(4)
        df["bb_lower"] = bb.bollinger_lband().round(4)
    except Exception as e:
        logger.warning(f"Indicator computation failed: {e}")
    return df


@router.get("/{symbol}", response_model=MarketDataResponse)
async def get_market_data(
    symbol: str,
    days: int = Query(90, ge=1, le=365),
):
    symbol = symbol.upper()
    yf_symbol = symbol  # default

    # Map UI symbol to yfinance ticker
    _alias = {"BTC": "BTC-USD", "ETH": "ETH-USD", "EURUSD": "EURUSD=X"}
    yf_symbol = _alias.get(symbol, symbol)

    if symbol not in VALID_SYMBOLS and yf_symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not tracked. Supported: {', '.join(sorted(VALID_SYMBOLS))}"
        )

    # Try live Yahoo Finance
    try:
        df = _fetch_yfinance(yf_symbol, days)
        if not df.empty:
            df = _add_indicators(df)
            bars = []
            for row in df.to_dict(orient="records"):
                bars.append(OHLCVBar(
                    date=str(row["date"]),
                    open=round(float(row["open"]), 4),
                    high=round(float(row["high"]), 4),
                    low=round(float(row["low"]), 4),
                    close=round(float(row["close"]), 4),
                    volume=int(row["volume"]),
                    rsi_14=row.get("rsi_14"),
                    macd=row.get("macd"),
                    macd_signal=row.get("macd_signal"),
                    bb_upper=row.get("bb_upper"),
                    bb_lower=row.get("bb_lower"),
                ))
            logger.info(f"Live market data: {symbol} — {len(bars)} bars")
            return MarketDataResponse(symbol=symbol, days=days, count=len(bars), data=bars)
    except Exception as e:
        logger.warning(f"yfinance failed for {symbol}: {e}")

    raise HTTPException(status_code=503, detail=f"Could not fetch live data for {symbol}")
