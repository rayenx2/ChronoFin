"""
Simulated real-time streaming producer.
Publishes micro-batches to Kafka to simulate a live market feed.
"""
import json
import time
import random
from datetime import datetime
from loguru import logger
from kafka import KafkaProducer
from kafka.errors import KafkaError

from data_ingestion.config import settings


class StockStreamProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
            retries=5,
            acks="all",
        )
        self.base_prices = {
            "AAPL": 185.0,
            "GOOGL": 140.0,
            "MSFT": 375.0,
            "AMZN": 175.0,
            "META": 490.0,
        }

    def _simulate_tick(self, symbol: str, base_price: float) -> dict:
        """Random walk with slight upward drift."""
        change_pct = random.gauss(0.0001, 0.002)
        price = round(base_price * (1 + change_pct), 2)
        self.base_prices[symbol] = price
        return {
            "symbol": symbol,
            "price": price,
            "volume": random.randint(1000, 50000),
            "bid": round(price - random.uniform(0.01, 0.05), 2),
            "ask": round(price + random.uniform(0.01, 0.05), 2),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "simulated_stream",
        }

    def stream(self, interval_seconds: float = 1.0, duration_seconds: int = 3600):
        logger.info(f"Streaming {list(self.base_prices.keys())} to Kafka topic '{settings.kafka.topic_raw}'...")
        end_time = time.time() + duration_seconds
        ticks_sent = 0

        while time.time() < end_time:
            for symbol, base_price in self.base_prices.items():
                tick = self._simulate_tick(symbol, base_price)
                try:
                    self.producer.send(
                        settings.kafka.topic_raw,
                        key=symbol,
                        value=tick,
                    )
                    ticks_sent += 1
                except KafkaError as e:
                    logger.error(f"Kafka send failed for {symbol}: {e}")

            self.producer.flush()
            if ticks_sent % 100 == 0:
                logger.debug(f"Ticks sent so far: {ticks_sent}")
            time.sleep(interval_seconds)

        logger.info(f"Stream complete. Total ticks sent: {ticks_sent}")

    def close(self):
        self.producer.close()
        logger.info("Kafka producer closed")


if __name__ == "__main__":
    producer = StockStreamProducer()
    try:
        producer.stream(interval_seconds=1.0, duration_seconds=300)
    finally:
        producer.close()
