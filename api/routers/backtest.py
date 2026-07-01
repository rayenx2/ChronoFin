"""Walk-forward backtest — real XGBoost on Yahoo Finance data."""
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from loguru import logger

from data_storage.cache import get_value, set_value

router = APIRouter()

_ALIAS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "EURUSD": "EURUSD=X"}
SUPPORTED = {"AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "NVDA", "BTC", "ETH", "EURUSD"}

FEATURES = [
    "open", "high", "low", "volume", "rsi", "macd", "macd_signal",
    "bb_upper", "bb_lower", "bb_width", "atr", "ret_1", "ret_5",
    "sma_10", "sma_20", "vol_ratio",
]


def _fetch_engineered(yf_symbol: str) -> pd.DataFrame:
    import yfinance as yf
    import ta
    df = yf.Ticker(yf_symbol).history(period="2y", interval="1d")
    if df.empty:
        raise ValueError("No data")
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
    df["vol_ratio"] = np.where(vol_ma == 0, 1.0, df["volume"] / vol_ma)
    return df.dropna().reset_index(drop=True)


def _sharpe(rets: np.ndarray, rf_daily: float = 0.02 / 252) -> float:
    excess = rets - rf_daily
    s = np.std(excess, ddof=1)
    return float(np.mean(excess) / s * np.sqrt(252)) if s > 1e-10 else 0.0


@router.get("/{symbol}")
async def get_backtest(symbol: str):
    symbol = symbol.upper()
    if symbol not in SUPPORTED:
        raise HTTPException(404, f"Symbol '{symbol}' not supported")

    cached = get_value(f"backtest:{symbol}")
    if cached:
        return cached

    from xgboost import XGBRegressor
    yf_symbol = _ALIAS.get(symbol, symbol)

    try:
        df = _fetch_engineered(yf_symbol)
    except Exception as e:
        raise HTTPException(503, f"Data fetch failed: {e}")

    if len(df) < 60:
        raise HTTPException(422, f"Not enough data for backtest: {len(df)} rows")

    df = df.copy()
    df["target"] = df["close"].shift(-1)
    df = df.dropna()

    X = df[FEATURES].values
    y = df["target"].values
    closes = df["close"].values
    dates = [str(d) for d in df["date"].values]

    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    closes_test = closes[split:]
    dates_test = dates[split:]

    model = XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
    )
    model.fit(X_train, y_train, verbose=False)
    preds = model.predict(X_test)

    mae = float(np.mean(np.abs(preds - y_test)))
    naive_mae = float(np.mean(np.abs(closes_test - y_test)))

    actual_dir = np.sign(y_test - closes_test)
    pred_dir = np.sign(preds - closes_test)
    dir_acc = float(np.mean(actual_dir == pred_dir))

    strategy_returns = np.where(preds > closes_test, (y_test - closes_test) / closes_test, 0.0)
    buy_hold_returns = (y_test - closes_test) / closes_test

    equity = [1.0]
    for r in strategy_returns:
        equity.append(equity[-1] * (1 + r))

    step = max(1, len(dates_test) // 60)
    chart_data = [
        {
            "date": dates_test[i],
            "actual": round(float(y_test[i]), 4),
            "predicted": round(float(preds[i]), 4),
            "equity": round(equity[i], 4),
        }
        for i in range(0, len(dates_test), step)
    ]

    result = {
        "symbol": symbol,
        "train_days": split,
        "test_days": len(X_test),
        "mae": round(mae, 4),
        "naive_mae": round(naive_mae, 4),
        "mae_vs_naive_pct": round((naive_mae - mae) / naive_mae * 100, 2),
        "directional_accuracy": round(dir_acc * 100, 2),
        "strategy_sharpe": round(_sharpe(strategy_returns), 3),
        "buyhold_sharpe": round(_sharpe(buy_hold_returns), 3),
        "final_equity": round(equity[-1], 4),
        "chart": chart_data,
    }

    set_value(f"backtest:{symbol}", result, 86400)
    logger.success(
        f"Backtest {symbol}: dir_acc={dir_acc:.1%} sharpe={result['strategy_sharpe']:.2f}"
    )
    return result
