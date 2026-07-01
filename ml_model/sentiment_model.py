"""
FinBERT-based sentiment scoring for financial news headlines.
Aggregates per-symbol daily sentiment as an additional trading signal.
"""
import torch
import pandas as pd
from loguru import logger

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not installed — sentiment model disabled")


class FinancialSentimentAnalyzer:
    MODEL_NAME = "ProsusAI/finbert"
    LABELS = ["positive", "negative", "neutral"]

    def __init__(self):
        if not TRANSFORMERS_AVAILABLE:
            raise RuntimeError("Install transformers: pip install transformers")
        logger.info("Loading FinBERT model (first run downloads ~440 MB)...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_NAME)
        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        logger.success(f"FinBERT loaded on {self.device}")

    def score(self, texts: list[str]) -> list[dict]:
        results = []
        for batch in self._batch(texts, size=16):
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                logits = self.model(**encoded).logits
            probs = torch.softmax(logits, dim=-1).cpu().tolist()
            for p in probs:
                scores = dict(zip(self.LABELS, p))
                scores["compound"] = scores["positive"] - scores["negative"]
                results.append(scores)
        return results

    def aggregate_daily(self, news_df: pd.DataFrame) -> pd.DataFrame:
        """
        news_df must have: symbol, date, headline columns.
        Returns daily sentiment aggregated per symbol.
        """
        if news_df.empty:
            return pd.DataFrame(columns=["symbol", "date",
                                         "sentiment_compound",
                                         "sentiment_positive",
                                         "sentiment_negative"])
        news_df = news_df.copy()
        headlines = news_df["headline"].tolist()
        scored = self.score(headlines)
        news_df["sentiment_compound"]  = [s["compound"]  for s in scored]
        news_df["sentiment_positive"]  = [s["positive"]  for s in scored]
        news_df["sentiment_negative"]  = [s["negative"]  for s in scored]
        return (
            news_df.groupby(["symbol", "date"])[
                ["sentiment_compound", "sentiment_positive", "sentiment_negative"]
            ]
            .mean()
            .reset_index()
        )

    @staticmethod
    def _batch(lst: list, size: int):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]


def fallback_sentiment(headline: str) -> dict:
    """
    Keyword-based fallback when FinBERT is unavailable.
    Very simple — useful for CI/CD and testing only.
    """
    positive_words = {"rise", "gain", "beat", "profit", "growth", "up", "record", "strong"}
    negative_words = {"fall", "drop", "miss", "loss", "decline", "down", "weak", "cut"}
    tokens = set(headline.lower().split())
    pos = len(tokens & positive_words)
    neg = len(tokens & negative_words)
    total = pos + neg or 1
    return {
        "positive": pos / total,
        "negative": neg / total,
        "neutral":  1 - (pos + neg) / total,
        "compound": (pos - neg) / total,
    }
