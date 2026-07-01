"""
FastAPI application: serves predictions, market data, sentiment, backtest, portfolio, and health checks.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger

from api.middleware import RequestLoggingMiddleware
from api.routers import predictions, market_data, sentiment, backtest, portfolio


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ChronoFin API starting...")
    yield
    logger.info("ChronoFin API shutting down...")


app = FastAPI(
    title="ChronoFin API",
    description="Real-time stock data and AI price predictions — by Rayen Lassoued",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["predictions"])
app.include_router(market_data.router, prefix="/api/v1/market",      tags=["market"])
app.include_router(sentiment.router,   prefix="/api/v1/sentiment",   tags=["sentiment"])
app.include_router(backtest.router,    prefix="/api/v1/backtest",     tags=["backtest"])
app.include_router(portfolio.router,   prefix="/api/v1/portfolio",    tags=["portfolio"])

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus metrics exposed at /metrics")
except ImportError:
    logger.warning("prometheus_fastapi_instrumentator not installed — /metrics disabled")


@app.get("/health", tags=["health"])
async def health():
    from data_storage.cache import health_check
    return {
        "status": "ok",
        "version": "1.0.0",
        "redis": "ok" if health_check() else "unavailable",
    }
