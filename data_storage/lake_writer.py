"""
Raw data lake writer.
Writes partitioned parquet to local filesystem or MinIO (S3-compatible).
"""
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from loguru import logger


LAKE_PATH = os.getenv("LAKE_PATH", "./data/raw_lake")


def write_to_lake(df: pd.DataFrame, partition: str, lake_path: str = LAKE_PATH) -> str:
    """
    Write DataFrame as parquet to the raw data lake.
    Path format: {lake_path}/{partition}/YYYY-MM-DD/data.parquet
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    output_dir = Path(lake_path) / partition / today
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "data.parquet"

    df.to_parquet(output_file, index=False, compression="snappy")
    size_kb = output_file.stat().st_size / 1024
    logger.info(f"Written {len(df)} rows → {output_file} ({size_kb:.1f} KB)")
    return str(output_file)


def read_from_lake(
    partition: str,
    date_str: str | None = None,
    lake_path: str = LAKE_PATH,
) -> pd.DataFrame:
    """Read parquet files from the lake. If date_str is None, reads all dates."""
    base = Path(lake_path) / partition
    if date_str:
        paths = list((base / date_str).glob("*.parquet"))
    else:
        paths = list(base.rglob("*.parquet"))

    if not paths:
        logger.warning(f"No parquet files found at {base}")
        return pd.DataFrame()

    frames = [pd.read_parquet(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Read {len(df)} rows from lake partition={partition}")
    return df
