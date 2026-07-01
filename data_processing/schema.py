"""Pydantic models for data validation at ingestion and serving boundaries."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StockPrice(BaseModel):
    symbol: str
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    adjusted_close: float = Field(gt=0)
    volume: int = Field(ge=0)
    ingested_at: Optional[datetime] = None

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v, info):
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("high must be >= low")
        return v


class StockTick(BaseModel):
    symbol: str
    price: float = Field(gt=0)
    volume: int = Field(ge=0)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    timestamp: datetime
    source: str = "unknown"


class TechnicalIndicators(BaseModel):
    symbol: str
    date: date
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    return_1d: Optional[float] = None
    return_5d: Optional[float] = None
