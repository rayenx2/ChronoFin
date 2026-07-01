"""
Inference pipeline: load trained models and produce next-day price predictions.
Writes results to Redis cache and PostgreSQL predictions table.
"""
import os
import pickle
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd
from loguru import logger
from xgboost import XGBRegressor

from data_storage.cache import cache_prediction
from data_storage.warehouse import upsert_predictions

try:
    import torch
    from ml_model.train import LSTMModel, FEATURES, TARGET, LOOKBACK, make_sequences
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    FEATURES = ["open", "high", "low", "volume", "sma_20", "sma_50", "rsi", "macd",
                "bb_upper", "bb_lower", "atr", "vwap", "sentiment_score", "returns"]
    TARGET = "close"
    LOOKBACK = 30

MODEL_DIR = Path(os.getenv("MODEL_DIR", "./models"))
MODEL_VERSION = "v1.0"


def _load_artifacts(symbol: str) -> tuple:
    if not _TORCH_AVAILABLE:
        raise FileNotFoundError(f"No trained model for {symbol}. Run: python -m ml_model.train")

    scaler_path = MODEL_DIR / f"scaler_{symbol}.pkl"
    xgb_path    = MODEL_DIR / f"xgb_{symbol}.json"
    lstm_path   = MODEL_DIR / f"lstm_{symbol}_best.pt"

    if not scaler_path.exists():
        raise FileNotFoundError(f"No artifacts for {symbol}. Run training first.")

    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)

    xgb = XGBRegressor()
    xgb.load_model(str(xgb_path))

    input_size = len(FEATURES)
    lstm = LSTMModel(input_size=input_size)
    lstm.load_state_dict(
        torch.load(lstm_path, map_location="cpu")
    )
    lstm.eval()

    return scaler, lstm, xgb


def predict_next_day(symbol: str, df: pd.DataFrame | None = None) -> dict:
    """
    Predict next trading day's closing price for a given symbol.
    If df is not provided, loads from the processed parquet store.
    """
    symbol = symbol.upper()
    scaler, lstm, xgb = _load_artifacts(symbol)

    if df is None:
        processed_path = os.getenv("PROCESSED_PATH", "./data/processed")
        df = pd.read_parquet(processed_path)

    sym_df = (
        df[df["symbol"] == symbol]
        .dropna(subset=FEATURES + [TARGET])
        .sort_values("date")
        .tail(LOOKBACK + 10)
        .reset_index(drop=True)
    )

    if len(sym_df) < LOOKBACK:
        raise ValueError(f"Not enough rows for {symbol}: need {LOOKBACK}, got {len(sym_df)}")

    feature_cols = FEATURES + [TARGET]
    scaled = scaler.transform(sym_df[feature_cols].values)
    X, _ = make_sequences(scaled, LOOKBACK)
    X_last = X[-1:]  # Shape: (1, LOOKBACK, n_features)

    # LSTM prediction
    with torch.no_grad():  # type: ignore[name-defined]
        lstm_pred_scaled = lstm(torch.FloatTensor(X_last)).item()  # type: ignore[name-defined]

    # XGBoost prediction
    xgb_pred_scaled = float(xgb.predict(X_last.reshape(1, -1))[0])

    # Ensemble blend
    blend_scaled = 0.6 * lstm_pred_scaled + 0.4 * xgb_pred_scaled

    # Invert scaling
    n_features = len(feature_cols)
    dummy = np.zeros((1, n_features))
    dummy[0, -1] = blend_scaled
    predicted_price = float(scaler.inverse_transform(dummy)[0, -1])

    current_price = float(sym_df["close"].iloc[-1])
    std_dev = float(sym_df["close"].tail(20).std())
    confidence_lower = round(predicted_price - 1.96 * std_dev, 4)
    confidence_upper = round(predicted_price + 1.96 * std_dev, 4)

    # Confidence score: narrower CI relative to price = higher confidence
    ci_width_pct = (confidence_upper - confidence_lower) / current_price
    confidence_score = round(max(0.0, min(1.0, 1.0 - ci_width_pct)), 4)

    prediction_date = (date.today() + timedelta(days=1)).isoformat()

    result = {
        "symbol": symbol,
        "current_price": round(current_price, 4),
        "predicted_price": round(predicted_price, 4),
        "confidence_lower": confidence_lower,
        "confidence_upper": confidence_upper,
        "confidence_score": confidence_score,
        "prediction_date": prediction_date,
        "model_version": MODEL_VERSION,
        "sentiment_score": None,
        "sentiment_label": "Neutral",
        "model_trained_at": "see MLflow",
    }

    cache_prediction(symbol, result)
    logger.info(f"{symbol}: predicted ${predicted_price:.2f} (current ${current_price:.2f})")
    return result


def batch_predict(symbols: list[str]) -> list[dict]:
    """Run inference for all symbols and persist to warehouse."""
    results = []
    df = pd.read_parquet(os.getenv("PROCESSED_PATH", "./data/processed"))
    for sym in symbols:
        try:
            pred = predict_next_day(sym, df=df)
            results.append(pred)
        except FileNotFoundError:
            logger.warning(f"No model found for {sym} — skipping inference")
        except Exception as e:
            logger.error(f"Inference failed for {sym}: {e}")

    if results:
        warehouse_records = [
            {
                "symbol": r["symbol"],
                "prediction_date": r["prediction_date"],
                "predicted_price": r["predicted_price"],
                "confidence_lower": r["confidence_lower"],
                "confidence_upper": r["confidence_upper"],
                "confidence_score": r["confidence_score"],
                "model_version": r["model_version"],
                "sentiment_score": r.get("sentiment_score"),
                "sentiment_label": r.get("sentiment_label", "Neutral"),
            }
            for r in results
        ]
        try:
            upsert_predictions(warehouse_records)
        except Exception as e:
            logger.warning(f"Could not persist predictions to warehouse: {e}")

    logger.success(f"Batch inference complete: {len(results)}/{len(symbols)} succeeded")
    return results
