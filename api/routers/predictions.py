"""Predictions router — real XGBoost forecast trained on live Yahoo Finance data."""
from datetime import date, timedelta
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas import PredictionResponse
from data_storage.cache import get_cached_prediction, cache_prediction

router = APIRouter()

_ALIAS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "EURUSD": "EURUSD=X"}

SUPPORTED = {
    "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "NVDA",
    "BTC", "ETH", "EURUSD",
}


def _fetch_and_engineer(yf_symbol: str, lookback: int = 120) -> pd.DataFrame:
    import yfinance as yf
    import ta
    # Use 2y to ensure forex/crypto have enough rows after feature engineering drops NaN
    fetch_period = "2y"
    df = yf.Ticker(yf_symbol).history(period=fetch_period, interval="1d")
    if df.empty:
        raise ValueError(f"No data from Yahoo Finance for {yf_symbol}")
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    close = df["close"]
    df["rsi"] = ta.momentum.RSIIndicator(close, 14).rsi()
    macd = ta.trend.MACD(close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    bb = ta.volatility.BollingerBands(close, 20, 2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = bb.bollinger_wband()
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], close, 14).average_true_range()
    df["ret_1"] = close.pct_change(1)
    df["ret_5"] = close.pct_change(5)
    df["sma_10"] = close.rolling(10).mean()
    df["sma_20"] = close.rolling(20).mean()
    vol_ma = df["volume"].rolling(20).mean()
    # Forex volume is always 0 — avoid 0/0 NaN; use 1.0 as neutral sentinel
    df["vol_ratio"] = np.where(vol_ma == 0, 1.0, df["volume"] / vol_ma)
    df = df.dropna().tail(lookback).reset_index(drop=True)
    return df


def _train_and_predict(df: pd.DataFrame) -> tuple[float, float]:
    from xgboost import XGBRegressor

    FEATURES = ["open", "high", "low", "volume", "rsi", "macd", "macd_signal",
                 "bb_upper", "bb_lower", "bb_width", "atr", "ret_1", "ret_5",
                 "sma_10", "sma_20", "vol_ratio"]

    # Target: next-day close
    df = df.copy()
    df["target"] = df["close"].shift(-1)
    df = df.dropna()

    if len(df) < 10:
        raise ValueError(f"Not enough data to train: only {len(df)} rows available")

    X = df[FEATURES].values
    y = df["target"].values

    # Walk-forward: train on 80%, test on 20% to get MAE
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05,
                          subsample=0.8, colsample_bytree=0.8, random_state=42)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    # Predict next day using the last row
    last_row = df.iloc[-1][FEATURES].values.reshape(1, -1)
    predicted = float(model.predict(last_row)[0])

    # MAE on test set
    test_preds = model.predict(X_test)
    mae = float(np.mean(np.abs(test_preds - y_test)))

    return predicted, mae


@router.get("/{symbol}", response_model=PredictionResponse)
async def get_prediction(
    symbol: str,
    force_refresh: bool = Query(False, description="Bypass Redis cache"),
):
    symbol = symbol.upper()
    if symbol not in SUPPORTED:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not supported. Supported: {', '.join(sorted(SUPPORTED))}"
        )

    if not force_refresh:
        cached = get_cached_prediction(symbol)
        if cached:
            logger.debug(f"Cache HIT for {symbol}")
            return PredictionResponse(**cached)

    yf_symbol = _ALIAS.get(symbol, symbol)

    try:
        logger.info(f"Fetching live data + training XGBoost for {symbol}...")
        df = _fetch_and_engineer(yf_symbol, lookback=60)
        predicted_price, mae = _train_and_predict(df)

        current_price = float(df["close"].iloc[-1])
        std = float(df["close"].tail(20).std())
        ci_lower = round(predicted_price - 1.96 * std, 4)
        ci_upper = round(predicted_price + 1.96 * std, 4)
        ci_width_pct = (ci_upper - ci_lower) / current_price if current_price else 0.1
        confidence = round(max(0.0, min(1.0, 1.0 - ci_width_pct)), 4)

        result = {
            "symbol": symbol,
            "current_price": round(current_price, 4),
            "predicted_price": round(predicted_price, 4),
            "confidence_lower": ci_lower,
            "confidence_upper": ci_upper,
            "confidence_score": confidence,
            "prediction_date": (date.today() + timedelta(days=1)).isoformat(),
            "model_version": "xgb-live-v1",
            "sentiment_score": None,
            "sentiment_label": "Neutral",
            "model_trained_at": date.today().isoformat(),
        }

        cache_prediction(symbol, result)
        logger.success(f"{symbol}: current=${current_price:.2f}, predicted=${predicted_price:.2f}, MAE={mae:.2f}")
        return PredictionResponse(**result)

    except Exception as e:
        logger.error(f"Prediction failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/", response_model=list[PredictionResponse])
async def get_batch_predictions(
    symbols: str = Query(..., description="Comma-separated symbols, e.g. AAPL,MSFT"),
):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for sym in symbol_list:
        try:
            results.append(await get_prediction(sym))
        except HTTPException as e:
            logger.warning(f"Skipping {sym}: {e.detail}")
    return results
