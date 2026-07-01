"""
PySpark ETL: clean raw parquet, enforce schema, deduplicate, and write to DW.
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, LongType, TimestampType
)
from loguru import logger

from data_processing.feature_engineering import add_technical_indicators


RAW_SCHEMA = StructType([
    StructField("symbol",         StringType(),    False),
    StructField("date",           TimestampType(), False),
    StructField("open",           DoubleType(),    True),
    StructField("high",           DoubleType(),    True),
    StructField("low",            DoubleType(),    True),
    StructField("close",          DoubleType(),    True),
    StructField("adjusted_close", DoubleType(),    True),
    StructField("volume",         LongType(),      True),
    StructField("ingested_at",    TimestampType(), True),
])


def get_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("ChronoFinAI")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def read_raw(spark: SparkSession, lake_path: str) -> DataFrame:
    logger.info(f"Reading raw parquet from {lake_path}")
    return spark.read.schema(RAW_SCHEMA).parquet(lake_path)


def clean(df: DataFrame) -> DataFrame:
    """Remove nulls, outliers, and deduplicate."""
    before = df.count()
    df = df.dropDuplicates(["symbol", "date"])
    df = df.filter(
        F.col("close").isNotNull() &
        F.col("volume").isNotNull() &
        (F.col("close") > 0) &
        (F.col("volume") > 0) &
        (F.col("high") >= F.col("low"))
    )
    # Reject extreme price moves > 50% in a single day (data quality)
    df = df.withColumn(
        "daily_return",
        (F.col("close") - F.col("open")) / F.col("open")
    ).filter(F.abs(F.col("daily_return")) < 0.5)

    after = df.count()
    logger.info(f"Cleaned: {before} → {after} rows ({before - after} dropped)")
    return df


def transform(df: DataFrame) -> DataFrame:
    """Add derived columns."""
    return df.withColumns({
        "price_range":  F.col("high") - F.col("low"),
        "vwap":         (F.col("high") + F.col("low") + F.col("close")) / 3,
        "year":         F.year("date"),
        "month":        F.month("date"),
        "day_of_week":  F.dayofweek("date"),
        "processed_at": F.current_timestamp(),
    })


def run_etl(lake_path: str, output_path: str) -> None:
    spark = get_spark()
    try:
        df = read_raw(spark, lake_path)
        df = clean(df)
        df = transform(df)
        df = add_technical_indicators(df, spark)
        (
            df.write
            .mode("overwrite")
            .partitionBy("year", "month", "symbol")
            .parquet(output_path)
        )
        count = df.count()
        logger.success(f"ETL complete. Wrote {count} rows to {output_path}")
    finally:
        spark.stop()


if __name__ == "__main__":
    run_etl("./data/raw_lake", "./data/processed")
