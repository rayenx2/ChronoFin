"""Markowitz portfolio optimization on live Yahoo Finance returns."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from data_storage.cache import get_value, set_value
from scripts.portfolio_optimizer import optimize_weights, calculate_returns

router = APIRouter()

STOCK_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "NVDA"]


def _fetch_prices(symbol: str, days: int) -> np.ndarray:
    import yfinance as yf
    df = yf.Ticker(symbol).history(period=f"{days + 30}d", interval="1d")
    if df.empty:
        raise ValueError(f"No price data for {symbol}")
    return df["Close"].values[-days:]


@router.get("/optimize")
async def optimize_portfolio(
    days: int = Query(252, ge=60, le=504),
    force_refresh: bool = Query(False),
):
    cache_key = f"portfolio:optimize:{days}"
    if not force_refresh:
        cached = get_value(cache_key)
        if cached:
            return cached

    logger.info(f"Fetching {days}-day returns for portfolio optimization...")

    prices = {}
    for sym in STOCK_SYMBOLS:
        try:
            prices[sym] = _fetch_prices(sym, days)
        except Exception as e:
            logger.warning(f"Skipping {sym}: {e}")

    if len(prices) < 2:
        raise HTTPException(503, "Not enough price data for optimization")

    min_len = min(len(v) for v in prices.values())
    assets_returns = {
        sym: calculate_returns(p[-min_len:])
        for sym, p in prices.items()
    }

    try:
        result = optimize_weights(assets_returns, n_portfolios=10_000)
    except Exception as e:
        raise HTTPException(500, f"Optimization failed: {e}")

    rng = np.random.default_rng(42)
    n = len(result.assets)
    returns_matrix = np.column_stack([assets_returns[a] for a in result.assets])
    ann_mean = np.mean(returns_matrix, axis=0) * 252
    cov = np.cov(returns_matrix.T, ddof=1) * 252

    raw = rng.exponential(1.0, (500, n))
    mc_w = raw / raw.sum(axis=1, keepdims=True)
    mc_ret = (mc_w @ ann_mean).tolist()
    mc_vol = [float(np.sqrt(max(w @ cov @ w, 0))) for w in mc_w]

    response = {
        "symbols": result.assets,
        "weights": [round(float(w), 4) for w in result.weights],
        "expected_return": round(result.expected_return * 100, 2),
        "volatility": round(result.volatility * 100, 2),
        "sharpe": round(result.sharpe, 3),
        "eq_return": round(result.eq_return * 100, 2),
        "eq_volatility": round(result.eq_volatility * 100, 2),
        "eq_sharpe": round(result.eq_sharpe, 3),
        "sharpe_improvement": round(
            (result.sharpe - result.eq_sharpe) / abs(result.eq_sharpe) * 100, 1
        ),
        "days_used": min_len,
        "frontier": [
            {"ret": round(r * 100, 2), "vol": round(v * 100, 2)}
            for r, v in zip(mc_ret, mc_vol)
        ],
    }

    set_value(cache_key, response, 3600)
    logger.success(f"Portfolio optimized: Sharpe={result.sharpe:.3f} vs eq={result.eq_sharpe:.3f}")
    return response
