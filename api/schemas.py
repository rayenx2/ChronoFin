"""Pydantic response schemas for the FastAPI layer."""
from typing import Optional
from pydantic import BaseModel


class PredictionResponse(BaseModel):
    symbol: str
    current_price: float
    predicted_price: float
    confidence_lower: float
    confidence_upper: float
    confidence_score: float
    prediction_date: str
    model_version: str
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = "Neutral"
    model_trained_at: Optional[str] = None


class OHLCVBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None


class MarketDataResponse(BaseModel):
    symbol: str
    days: int
    count: int
    data: list[OHLCVBar]
