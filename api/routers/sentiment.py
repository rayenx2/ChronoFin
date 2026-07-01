"""News sentiment via VADER — no GPU required."""
from fastapi import APIRouter, HTTPException
from loguru import logger

from data_storage.cache import get_value, set_value

router = APIRouter()

_ALIAS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "EURUSD": "EURUSD=X"}
SUPPORTED = {"AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "NVDA", "BTC", "ETH", "EURUSD"}


def _vader_score(text: str) -> float:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
        return sia.polarity_scores(text)["compound"]
    except Exception:
        pos = {"rise", "gain", "beat", "profit", "growth", "up", "record", "strong",
               "bull", "surge", "soar", "rally", "high", "positive", "buy"}
        neg = {"fall", "drop", "miss", "loss", "decline", "down", "weak", "cut",
               "bear", "crash", "plunge", "slump", "low", "negative", "sell"}
        tokens = set(text.lower().split())
        p = len(tokens & pos)
        n = len(tokens & neg)
        return (p - n) / max(p + n, 1)


@router.get("/{symbol}")
async def get_sentiment(symbol: str):
    symbol = symbol.upper()
    if symbol not in SUPPORTED:
        raise HTTPException(404, f"Symbol '{symbol}' not supported")

    cached = get_value(f"sentiment:{symbol}")
    if cached:
        return cached

    import yfinance as yf
    yf_symbol = _ALIAS.get(symbol, symbol)

    try:
        news = yf.Ticker(yf_symbol).news or []
    except Exception as e:
        raise HTTPException(503, f"Could not fetch news: {e}")

    articles = []
    for item in news[:15]:
        # Support both old flat format and new nested content format
        content = item.get("content", item)
        title = content.get("title", "") or item.get("title", "")
        if not title:
            continue
        provider = content.get("provider", {})
        publisher = provider.get("displayName", "") or item.get("publisher", "")
        url_obj = content.get("canonicalUrl", content.get("clickThroughUrl", {}))
        url = url_obj.get("url", "") if isinstance(url_obj, dict) else item.get("link", "")
        score = _vader_score(title)
        label = "Bullish" if score > 0.05 else ("Bearish" if score < -0.05 else "Neutral")
        articles.append({
            "title": title,
            "publisher": publisher,
            "url": url,
            "published_at": content.get("pubDate", item.get("providerPublishTime", "")),
            "sentiment_score": round(score, 4),
            "sentiment_label": label,
        })

    if not articles:
        result = {
            "symbol": symbol,
            "articles": [],
            "aggregate_score": 0.0,
            "aggregate_label": "Neutral",
            "article_count": 0,
        }
    else:
        scores = [a["sentiment_score"] for a in articles]
        agg = sum(scores) / len(scores)
        result = {
            "symbol": symbol,
            "articles": articles,
            "aggregate_score": round(agg, 4),
            "aggregate_label": "Bullish" if agg > 0.05 else ("Bearish" if agg < -0.05 else "Neutral"),
            "article_count": len(articles),
        }

    set_value(f"sentiment:{symbol}", result, 1800)
    logger.info(f"Sentiment {symbol}: {result['aggregate_label']} ({result['aggregate_score']:.3f})")
    return result
