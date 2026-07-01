"""
ChronoFin — Markowitz Mean-Variance Portfolio Optimizer

Finds portfolio weights that maximize the Sharpe ratio via Monte Carlo simulation.
Uses only numpy — no scipy or other optimization libraries required.

Usage:
    python scripts/portfolio_optimizer.py --demo
    python scripts/portfolio_optimizer.py --symbols AAPL MSFT GOOGL --days 252

Author: Rayen Lassoued | github.com/Hamilas
"""
from __future__ import annotations

import argparse
import sys
from typing import NamedTuple

import numpy as np


# ── Types ──────────────────────────────────────────────────────────────────────

class PortfolioResult(NamedTuple):
    weights: np.ndarray        # optimal allocation per asset
    assets: list[str]          # asset names matching weights
    expected_return: float     # annualized expected return
    volatility: float          # annualized standard deviation
    sharpe: float              # Sharpe ratio (excess return / volatility)
    eq_return: float           # equal-weight baseline return
    eq_volatility: float       # equal-weight baseline volatility
    eq_sharpe: float           # equal-weight baseline Sharpe


# ── Core math ──────────────────────────────────────────────────────────────────

def calculate_returns(prices: np.ndarray) -> np.ndarray:
    """
    Compute daily log returns from a price series.

    Args:
        prices: 1D array of asset prices (length N)

    Returns:
        1D array of daily log returns (length N-1)
    """
    if len(prices) < 2:
        raise ValueError("Need at least 2 price points to compute returns")
    return np.log(prices[1:] / prices[:-1])


def calculate_sharpe(
    returns: np.ndarray,
    weights: np.ndarray,
    risk_free: float = 0.02,
    trading_days: int = 252,
) -> float:
    """
    Compute the annualized Sharpe ratio for a given portfolio.

    Args:
        returns: 2D array of shape (T, N) — daily returns for N assets
        weights: 1D array of length N summing to 1.0
        risk_free: Annual risk-free rate (default 2% — EU 10Y Bund approx)
        trading_days: Trading days per year (default 252)

    Returns:
        Sharpe ratio as a float (higher is better; >1.0 is considered good)
    """
    if returns.ndim == 1:
        returns = returns.reshape(-1, 1)
        weights = np.array([1.0])

    portfolio_daily_returns = returns @ weights
    ann_return = np.mean(portfolio_daily_returns) * trading_days
    ann_vol = np.std(portfolio_daily_returns, ddof=1) * np.sqrt(trading_days)

    if ann_vol < 1e-10:
        return 0.0
    return (ann_return - risk_free) / ann_vol


def _build_cov_matrix(returns: np.ndarray, trading_days: int = 252) -> np.ndarray:
    """Annualized covariance matrix from daily returns."""
    return np.cov(returns.T, ddof=1) * trading_days


def optimize_weights(
    assets_returns: dict[str, np.ndarray],
    n_portfolios: int = 10_000,
    risk_free: float = 0.02,
    trading_days: int = 252,
    seed: int = 42,
) -> PortfolioResult:
    """
    Find the portfolio weights that maximize the Sharpe ratio.

    Uses Monte Carlo simulation: samples `n_portfolios` random weight vectors
    and returns the one with the highest Sharpe ratio. This is the standard
    "efficient frontier" approach without requiring convex optimization.

    Args:
        assets_returns: Dict mapping asset name -> 1D array of daily returns
        n_portfolios: Number of random portfolios to evaluate (higher = more accurate)
        risk_free: Annual risk-free rate used in Sharpe calculation
        trading_days: Trading days per year for annualization
        seed: Random seed for reproducibility

    Returns:
        PortfolioResult with optimal weights and performance metrics

    Raises:
        ValueError: If fewer than 2 assets are provided
        ValueError: If return arrays have different lengths
    """
    assets = list(assets_returns.keys())
    n = len(assets)

    if n < 2:
        raise ValueError(f"Need at least 2 assets, got {n}")

    lengths = [len(r) for r in assets_returns.values()]
    if len(set(lengths)) > 1:
        raise ValueError(f"Return arrays have different lengths: {dict(zip(assets, lengths))}")

    returns_matrix = np.column_stack([assets_returns[a] for a in assets])

    ann_mean = np.mean(returns_matrix, axis=0) * trading_days
    cov = _build_cov_matrix(returns_matrix, trading_days)

    rng = np.random.default_rng(seed)

    # Monte Carlo: sample random Dirichlet-distributed weight vectors
    raw_weights = rng.exponential(1.0, size=(n_portfolios, n))
    weights_mc = raw_weights / raw_weights.sum(axis=1, keepdims=True)

    # Vectorized: compute return and volatility for all portfolios at once
    port_returns = weights_mc @ ann_mean                              # (n_portfolios,)
    port_vars = np.einsum("pi,ij,pj->p", weights_mc, cov, weights_mc)  # (n_portfolios,)
    port_vols = np.sqrt(np.maximum(port_vars, 0))                    # (n_portfolios,)

    sharpes = np.where(port_vols > 1e-10, (port_returns - risk_free) / port_vols, 0.0)
    best_idx = int(np.argmax(sharpes))

    opt_w = weights_mc[best_idx]
    opt_ret = float(port_returns[best_idx])
    opt_vol = float(port_vols[best_idx])
    opt_sharpe = float(sharpes[best_idx])

    # Equal-weight baseline
    eq_w = np.ones(n) / n
    eq_ret = float(eq_w @ ann_mean)
    eq_var = float(eq_w @ cov @ eq_w)
    eq_vol = float(np.sqrt(max(eq_var, 0)))
    eq_sharpe = float((eq_ret - risk_free) / eq_vol) if eq_vol > 1e-10 else 0.0

    return PortfolioResult(
        weights=opt_w,
        assets=assets,
        expected_return=opt_ret,
        volatility=opt_vol,
        sharpe=opt_sharpe,
        eq_return=eq_ret,
        eq_volatility=eq_vol,
        eq_sharpe=eq_sharpe,
    )


def format_portfolio(result: PortfolioResult) -> str:
    """
    Format a PortfolioResult as a human-readable string for CLI output.

    Args:
        result: PortfolioResult from optimize_weights()

    Returns:
        Formatted multi-line string
    """
    lines = [
        "",
        "=" * 55,
        "  FINANCEFLOW-AI — Markowitz Portfolio Optimizer",
        "=" * 55,
        "",
        "  OPTIMAL WEIGHTS (Max Sharpe Ratio):",
        "  " + "-" * 40,
    ]

    max_name_len = max(len(a) for a in result.assets)
    for asset, weight in zip(result.assets, result.weights):
        bar_len = int(weight * 30)
        bar = "#" * bar_len + " " * (30 - bar_len)
        lines.append(f"  {asset:<{max_name_len}}  [{bar}]  {weight*100:5.1f}%")

    lines += [
        "",
        "  OPTIMIZED PORTFOLIO          EQUAL-WEIGHT BASELINE",
        "  " + "-" * 50,
        f"  Return   : {result.expected_return*100:6.2f}%               {result.eq_return*100:6.2f}%",
        f"  Volatility: {result.volatility*100:6.2f}%               {result.eq_volatility*100:6.2f}%",
        f"  Sharpe   : {result.sharpe:6.3f}                {result.eq_sharpe:6.3f}",
        "",
    ]

    improvement = (result.sharpe - result.eq_sharpe) / abs(result.eq_sharpe) * 100
    lines += [
        f"  Sharpe improvement vs equal-weight: {improvement:+.1f}%",
        "",
        "=" * 55,
        "  Rayen Lassoued | github.com/Hamilas",
        "=" * 55,
        "",
    ]
    return "\n".join(lines)


# ── Demo data ──────────────────────────────────────────────────────────────────

def _generate_demo_prices(
    symbols: list[str],
    base_prices: dict[str, float],
    n_days: int = 504,
) -> dict[str, np.ndarray]:
    """Generate realistic synthetic price series for demo purposes."""
    np.random.seed(2024)
    prices = {}
    # Correlations: tech stocks correlate at ~0.6
    market_factor = np.random.normal(0.0003, 0.008, n_days)

    for sym in symbols:
        base = base_prices.get(sym, 100.0)
        idio = np.random.normal(0.0002, 0.012, n_days)
        daily = 0.55 * market_factor + 0.45 * idio
        price_series = base * np.cumprod(1 + daily)
        prices[sym] = price_series
    return prices


# ── CLI ────────────────────────────────────────────────────────────────────────

DEMO_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
DEMO_PRICES = {"AAPL": 185.0, "MSFT": 375.0, "GOOGL": 140.0, "AMZN": 175.0, "META": 490.0}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="ChronoFin Markowitz Portfolio Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/portfolio_optimizer.py --demo
  python scripts/portfolio_optimizer.py --symbols AAPL MSFT GOOGL
  python scripts/portfolio_optimizer.py --demo --n-portfolios 50000
        """,
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run with 5 pre-configured example stocks (AAPL, MSFT, GOOGL, AMZN, META)"
    )
    parser.add_argument(
        "--symbols", nargs="+", default=None,
        help="List of stock symbols (used with --demo for subset selection)"
    )
    parser.add_argument(
        "--days", type=int, default=504,
        help="Number of trading days to simulate (default: 504 = 2 years)"
    )
    parser.add_argument(
        "--n-portfolios", type=int, default=10_000,
        help="Monte Carlo portfolios to evaluate (default: 10000)"
    )
    parser.add_argument(
        "--risk-free", type=float, default=0.02,
        help="Annual risk-free rate (default: 0.02 = 2%% — EU 10Y Bund)"
    )

    args = parser.parse_args(argv)

    if not args.demo and not args.symbols:
        parser.print_help()
        print("\nERROR: Use --demo for example data, or provide --symbols with price data.")
        sys.exit(1)

    symbols = args.symbols if args.symbols else DEMO_SYMBOLS
    # Filter to known demo symbols
    symbols = [s.upper() for s in symbols if s.upper() in DEMO_PRICES]

    if len(symbols) < 2:
        print(f"ERROR: Need at least 2 valid demo symbols from {DEMO_SYMBOLS}")
        sys.exit(1)

    print(f"\nGenerating {args.days}-day synthetic price series for: {', '.join(symbols)}")
    prices = _generate_demo_prices(symbols, DEMO_PRICES, args.days)

    print(f"Computing returns and running {args.n_portfolios:,} Monte Carlo portfolios...")
    assets_returns = {
        sym: calculate_returns(price_series)
        for sym, price_series in prices.items()
    }

    result = optimize_weights(
        assets_returns,
        n_portfolios=args.n_portfolios,
        risk_free=args.risk_free,
    )

    print(format_portfolio(result))

    # Validate Sharpe computation matches
    test_sharpe = calculate_sharpe(
        np.column_stack(list(assets_returns.values())),
        result.weights,
        risk_free=args.risk_free,
    )
    assert abs(test_sharpe - result.sharpe) < 1e-6, f"Sharpe mismatch: {test_sharpe} vs {result.sharpe}"
    print(f"  [Sharpe verified: {test_sharpe:.4f}]")


if __name__ == "__main__":
    main()
