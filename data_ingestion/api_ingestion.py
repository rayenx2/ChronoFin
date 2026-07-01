"""
Batch ingestion from Alpha Vantage REST API.
Handles rate limits, retries, and raw parquet writes to the data lake.
"""
import time
import requests
import pandas as pd
from datetime import datetime
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from data_storage.lake_writer import write_to_lake


class AlphaVantageIngester:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _fetch_daily(self, symbol: str) -> dict:
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": self.api_key,
        }
        response = self.session.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "Error Message" in data:
            raise ValueError(f"API error for {symbol}: {data['Error Message']}")
        if "Note" in data:
            logger.warning(f"Rate limit hit for {symbol}. Sleeping 60s.")
            time.sleep(60)
            raise RuntimeError("Rate limit — retry triggered")

        return data

    def ingest_symbol(self, symbol: str) -> pd.DataFrame:
        logger.info(f"Ingesting {symbol}")
        raw = self._fetch_daily(symbol)
        ts = raw.get("Time Series (Daily)", {})

        records = []
        for date_str, ohlcv in ts.items():
            records.append({
                "symbol": symbol,
                "date": pd.to_datetime(date_str),
                "open": float(ohlcv["1. open"]),
                "high": float(ohlcv["2. high"]),
                "low": float(ohlcv["3. low"]),
                "close": float(ohlcv["4. close"]),
                "adjusted_close": float(ohlcv["5. adjusted close"]),
                "volume": int(ohlcv["6. volume"]),
                "ingested_at": datetime.utcnow(),
            })

        df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
        logger.success(f"Fetched {len(df)} rows for {symbol}")
        return df

    def ingest_all(self, symbols: list[str]) -> pd.DataFrame:
        frames = []
        for i, symbol in enumerate(symbols):
            try:
                df = self.ingest_symbol(symbol)
                frames.append(df)
                write_to_lake(df, partition=f"symbol={symbol}")
            except Exception as e:
                logger.error(f"Failed ingesting {symbol}: {e}")
            # Alpha Vantage free tier: 5 calls/min
            if i < len(symbols) - 1:
                time.sleep(12)

        if not frames:
            raise RuntimeError("All symbol ingestions failed")

        combined = pd.concat(frames, ignore_index=True)
        logger.info(f"Total rows ingested: {len(combined)}")
        return combined


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    ingester = AlphaVantageIngester(api_key=os.environ["ALPHA_VANTAGE_KEY"])
    df = ingester.ingest_all(["AAPL", "MSFT"])
    print(df.tail())
