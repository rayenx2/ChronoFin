"""Centralised settings loader using Pydantic Settings."""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaSettings(BaseSettings):
    bootstrap_servers: str = Field("localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    topic_raw: str = "stock_prices_raw"
    topic_processed: str = "stock_prices_processed"
    consumer_group: str = "stock_pipeline"


class StorageSettings(BaseSettings):
    lake_path: str = "./data/raw_lake"
    postgres_url: str = Field(..., validation_alias="POSTGRES_URL")
    redis_url: str = Field("redis://localhost:6379", validation_alias="REDIS_URL")
    minio_endpoint: str = Field("localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field("minioadmin", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field("minioadmin", validation_alias="MINIO_SECRET_KEY")


class Settings(BaseSettings):
    alpha_vantage_key: str = Field(..., validation_alias="ALPHA_VANTAGE_KEY")
    symbols: list[str] = ["AAPL", "GOOGL", "MSFT", "AMZN", "META"]
    log_level: str = "INFO"
    kafka: KafkaSettings = KafkaSettings()
    storage: StorageSettings = StorageSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
