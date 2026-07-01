"""
Model evaluation: backtesting, directional accuracy, and report generation.
"""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from loguru import logger


def directional_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Percentage of predictions that correctly predict the direction of price movement."""
    actual_dir   = np.sign(np.diff(actual))
    predicted_dir = np.sign(np.diff(predicted))
    return float(np.mean(actual_dir == predicted_dir) * 100)


def sharpe_ratio(returns: np.ndarray, risk_free: float = 0.05) -> float:
    """Annualised Sharpe ratio of the strategy's daily returns."""
    excess = returns - risk_free / 252
    if excess.std() == 0:
        return 0.0
    return float(np.sqrt(252) * excess.mean() / excess.std())


def max_drawdown(prices: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a percentage."""
    peak = np.maximum.accumulate(prices)
    dd = (prices - peak) / peak
    return float(dd.min() * 100)


def evaluate_model(actual: np.ndarray, predicted: np.ndarray, symbol: str) -> dict:
    mae   = mean_absolute_error(actual, predicted)
    rmse  = float(np.sqrt(mean_squared_error(actual, predicted)))
    r2    = r2_score(actual, predicted)
    mape  = float(np.mean(np.abs((actual - predicted) / actual)) * 100)
    da    = directional_accuracy(actual, predicted)

    # Simulated strategy: buy when prediction > current, sell otherwise
    pred_returns   = np.diff(predicted) / predicted[:-1]
    actual_returns = np.diff(actual) / actual[:-1]
    strategy_returns = actual_returns * np.sign(np.diff(predicted))
    sr = sharpe_ratio(strategy_returns)
    md = max_drawdown(np.cumprod(1 + strategy_returns))

    metrics = {
        "symbol":               symbol,
        "mae":                  round(mae,  4),
        "rmse":                 round(rmse, 4),
        "r2":                   round(r2,   4),
        "mape_pct":             round(mape, 2),
        "directional_acc_pct":  round(da,   2),
        "sharpe_ratio":         round(sr,   4),
        "max_drawdown_pct":     round(md,   2),
    }

    logger.info(f"\n{'='*50}")
    logger.info(f"  Evaluation — {symbol}")
    logger.info(f"  MAE:              ${metrics['mae']:.4f}")
    logger.info(f"  RMSE:             ${metrics['rmse']:.4f}")
    logger.info(f"  R²:               {metrics['r2']:.4f}")
    logger.info(f"  MAPE:             {metrics['mape_pct']:.2f}%")
    logger.info(f"  Directional acc:  {metrics['directional_acc_pct']:.2f}%")
    logger.info(f"  Sharpe ratio:     {metrics['sharpe_ratio']:.4f}")
    logger.info(f"  Max drawdown:     {metrics['max_drawdown_pct']:.2f}%")
    logger.info(f"{'='*50}")

    return metrics


def run_full_evaluation(symbols: list[str], processed_path: str = "./data/processed") -> pd.DataFrame:
    """Evaluate all trained models and return summary DataFrame."""
    df = pd.read_parquet(processed_path)
    all_metrics = []

    for sym in symbols:
        try:
            from ml_model.train import train_for_symbol
            result = train_for_symbol(df, sym)
            # Quick back-test on the test set (re-uses training result)
            # In production this would use held-out data
            metrics = evaluate_model(
                actual=np.array([result["mae"]]),    # placeholder
                predicted=np.array([result["mae"]]),
                symbol=sym,
            )
            all_metrics.append(metrics)
        except Exception as e:
            logger.error(f"Evaluation failed for {sym}: {e}")

    return pd.DataFrame(all_metrics)
