"""
Financial news ingestion from RSS feeds.
Feeds headlines into the sentiment pipeline.
"""
import feedparser
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger


RSS_FEEDS = {
    "AAPL":  "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL&region=US&lang=en-US",
    "GOOGL": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GOOGL&region=US&lang=en-US",
    "MSFT":  "https://feeds.finance.yahoo.com/rss/2.0/headline?s=MSFT&region=US&lang=en-US",
    "AMZN":  "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AMZN&region=US&lang=en-US",
    "META":  "https://feeds.finance.yahoo.com/rss/2.0/headline?s=META&region=US&lang=en-US",
}

FALLBACK_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]


class NewsIngester:
    def __init__(self, lookback_days: int = 7):
        self.lookback_days = lookback_days
        self.cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    def _parse_feed(self, symbol: str, url: str) -> list[dict]:
        records = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else datetime.utcnow()
                if published < self.cutoff:
                    continue
                feed_title = (
                    feed.feed.get("title", url)
                    if isinstance(feed.feed, dict)
                    else getattr(feed.feed, "title", url)
                )
                records.append({
                    "symbol": symbol,
                    "date": published.date(),
                    "headline": getattr(entry, "title", ""),
                    "summary": getattr(entry, "summary", "")[:500],
                    "url": getattr(entry, "link", ""),
                    "source": feed_title,
                    "ingested_at": datetime.utcnow(),
                })
        except Exception as e:
            logger.warning(f"RSS feed failed for {symbol}: {e}")
        return records

    def ingest_all(self) -> pd.DataFrame:
        all_records = []
        for symbol, url in RSS_FEEDS.items():
            logger.info(f"Fetching news for {symbol}")
            records = self._parse_feed(symbol, url)
            all_records.extend(records)
            logger.info(f"  Got {len(records)} articles for {symbol}")

        if not all_records:
            logger.warning("No news articles fetched. Returning empty DataFrame.")
            return pd.DataFrame(columns=["symbol", "date", "headline", "summary", "url", "source"])

        df = pd.DataFrame(all_records)
        df = df.drop_duplicates(subset=["symbol", "headline"])
        logger.success(f"Total news articles ingested: {len(df)}")
        return df


if __name__ == "__main__":
    ingester = NewsIngester(lookback_days=3)
    df = ingester.ingest_all()
    print(df[["symbol", "date", "headline"]].head(10))
