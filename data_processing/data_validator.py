"""
Great Expectations data validation suites.
Run after ETL to gate bad data from reaching the warehouse.
"""
import pandas as pd
from loguru import logger

try:
    import great_expectations as gx
    GX_AVAILABLE = True
except ImportError:
    GX_AVAILABLE = False
    logger.warning("great-expectations not installed. Using lightweight fallback validator.")


def run_validation_suite(processed_path: str) -> bool:
    """Returns True if all checks pass, False otherwise."""
    if GX_AVAILABLE:
        return _run_gx_suite(processed_path)
    return _run_fallback_suite(processed_path)


def _run_fallback_suite(processed_path: str) -> bool:
    """Lightweight pandas-based validation when GX is not available."""
    try:
        df = pd.read_parquet(processed_path)
    except Exception as e:
        logger.error(f"Cannot read processed data: {e}")
        return False

    checks = []

    # No nulls in key columns
    for col in ["symbol", "date", "close", "volume"]:
        null_count = df[col].isna().sum()
        passed = null_count == 0
        checks.append(("no_nulls_" + col, passed, f"{null_count} nulls"))
        if not passed:
            logger.warning(f"Check failed: {col} has {null_count} null values")

    # Close > 0
    neg_prices = (df["close"] <= 0).sum()
    checks.append(("close_positive", neg_prices == 0, f"{neg_prices} non-positive"))

    # Volume > 0
    neg_vol = (df["volume"] <= 0).sum()
    checks.append(("volume_positive", neg_vol == 0, f"{neg_vol} non-positive"))

    # No duplicate (symbol, date)
    dups = df.duplicated(subset=["symbol", "date"]).sum()
    checks.append(("no_duplicates", dups == 0, f"{dups} duplicates"))

    # RSI within [0, 100]
    if "rsi_14" in df.columns:
        bad_rsi = df["rsi_14"].dropna()
        bad_rsi = ((bad_rsi < 0) | (bad_rsi > 100)).sum()
        checks.append(("rsi_range", bad_rsi == 0, f"{bad_rsi} out of range"))

    passed_all = all(c[1] for c in checks)
    for name, passed, detail in checks:
        icon = "✓" if passed else "✗"
        logger.info(f"  {icon} {name}: {detail}")

    if passed_all:
        logger.success("All validation checks passed")
    else:
        logger.error("Validation failed — data quality issues detected")

    return passed_all


def _run_gx_suite(processed_path: str) -> bool:
    """Full Great Expectations suite."""
    try:
        context = gx.get_context()
        df = pd.read_parquet(processed_path)
        validator = context.sources.pandas_default.read_dataframe(df)

        validator.expect_column_values_to_not_be_null("symbol")
        validator.expect_column_values_to_not_be_null("date")
        validator.expect_column_values_to_not_be_null("close")
        validator.expect_column_values_to_be_between("close", min_value=0)
        validator.expect_column_values_to_be_between("volume", min_value=0)
        validator.expect_column_values_to_be_between("rsi_14", min_value=0, max_value=100)
        validator.expect_compound_columns_to_be_unique(["symbol", "date"])

        results = validator.validate()
        success = results["success"]
        logger.info(f"GX validation: {results['statistics']['successful_expectations']}/"
                    f"{results['statistics']['evaluated_expectations']} checks passed")
        return success
    except Exception as e:
        logger.error(f"GX validation error: {e}. Falling back to lightweight checks.")
        return _run_fallback_suite(processed_path)
