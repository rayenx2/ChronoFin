"""
PostgreSQL data warehouse writer.
Handles upserts for stock prices, technical indicators, and predictions.
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from loguru import logger


def get_engine():
    url = os.environ["POSTGRES_URL"]
    return create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True)


def upsert_stock_prices(df: pd.DataFrame) -> int:
    engine = get_engine()
    records = df[[
        "symbol", "date", "open", "high", "low",
        "close", "adjusted_close", "volume", "ingested_at",
    ]].to_dict(orient="records")

    stmt = insert(text("stock_prices")).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "date"],
        set_={
            "close": stmt.excluded.close,
            "adjusted_close": stmt.excluded.adjusted_close,
            "volume": stmt.excluded.volume,
        },
    )
    with engine.begin() as conn:
        result = conn.execute(stmt)
    logger.info(f"Upserted {result.rowcount} stock_prices rows")
    return result.rowcount


def upsert_indicators(df: pd.DataFrame) -> int:
    engine = get_engine()
    cols = [
        "symbol", "date", "rsi_14", "macd", "macd_signal",
        "macd_hist", "bb_upper", "bb_lower", "bb_width",
        "atr_14", "return_1d", "return_5d",
    ]
    available = [c for c in cols if c in df.columns]
    records = df[available].to_dict(orient="records")

    with engine.begin() as conn:
        for rec in records:
            conn.execute(
                text("""
                    INSERT INTO technical_indicators ({cols})
                    VALUES ({vals})
                    ON CONFLICT (symbol, date) DO UPDATE
                    SET {updates}
                """.format(
                    cols=", ".join(rec.keys()),
                    vals=", ".join(f":{k}" for k in rec.keys()),
                    updates=", ".join(f"{k}=EXCLUDED.{k}" for k in rec.keys()
                                     if k not in ("symbol", "date")),
                )),
                rec,
            )
    logger.info(f"Upserted {len(records)} indicator rows")
    return len(records)


def upsert_predictions(predictions: list[dict]) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        for pred in predictions:
            conn.execute(
                text("""
                    INSERT INTO predictions
                        (symbol, prediction_date, predicted_price,
                         confidence_lower, confidence_upper, confidence_score,
                         model_version, sentiment_score, sentiment_label)
                    VALUES
                        (:symbol, :prediction_date, :predicted_price,
                         :confidence_lower, :confidence_upper, :confidence_score,
                         :model_version, :sentiment_score, :sentiment_label)
                    ON CONFLICT (symbol, prediction_date, model_version)
                    DO UPDATE SET
                        predicted_price  = EXCLUDED.predicted_price,
                        confidence_lower = EXCLUDED.confidence_lower,
                        confidence_upper = EXCLUDED.confidence_upper,
                        confidence_score = EXCLUDED.confidence_score
                """),
                pred,
            )
    logger.info(f"Upserted {len(predictions)} prediction rows")
    return len(predictions)


def upsert_processed_data(processed_path: str) -> None:
    """Read processed parquet and write all tables to warehouse."""
    df = pd.read_parquet(processed_path)
    upsert_stock_prices(df)
    upsert_indicators(df)
    logger.success("Warehouse load complete")


def read_prices(symbol: str, days: int = 180) -> pd.DataFrame:
    engine = get_engine()
    query = text("""
        SELECT sp.*, ti.rsi_14, ti.macd, ti.macd_signal,
               ti.bb_upper, ti.bb_lower, ti.atr_14,
               ti.return_1d, ti.return_5d
        FROM stock_prices sp
        LEFT JOIN technical_indicators ti
            ON sp.symbol = ti.symbol AND sp.date = ti.date
        WHERE sp.symbol = :symbol
          AND sp.date >= CURRENT_DATE - INTERVAL ':days days'
        ORDER BY sp.date ASC
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(query, conn, params={"symbol": symbol, "days": days})
