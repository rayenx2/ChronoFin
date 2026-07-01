"""
Redis cache helpers.
Used for latest prices, predictions, and API response caching.
"""
import os
import json
from datetime import datetime
from typing import Any
import redis
from loguru import logger

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    return _client


def set_value(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    try:
        serialized = json.dumps(value, default=str)
        get_client().setex(key, ttl_seconds, serialized)
        return True
    except Exception as e:
        logger.warning(f"Cache set failed for {key}: {e}")
        return False


def get_value(key: str) -> Any | None:
    try:
        raw = get_client().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Cache get failed for {key}: {e}")
        return None


def delete_key(key: str) -> None:
    try:
        get_client().delete(key)
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")


def cache_prediction(symbol: str, prediction: dict, ttl: int = 3600) -> None:
    set_value(f"prediction:{symbol.upper()}", prediction, ttl)
    logger.debug(f"Cached prediction for {symbol} (TTL={ttl}s)")


def get_cached_prediction(symbol: str) -> dict | None:
    return get_value(f"prediction:{symbol.upper()}")


def cache_latest_price(symbol: str, price: float, ttl: int = 60) -> None:
    set_value(f"price:latest:{symbol.upper()}", {
        "price": price,
        "timestamp": datetime.utcnow().isoformat(),
    }, ttl)


def get_latest_price(symbol: str) -> dict | None:
    return get_value(f"price:latest:{symbol.upper()}")


def health_check() -> bool:
    try:
        return get_client().ping()
    except Exception:
        return False
