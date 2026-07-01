"""MLflow experiment tracking setup."""
import os
from loguru import logger


def setup_tracking(experiment_name: str = "chronofin") -> None:
    import mlflow

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    try:
        mlflow.set_experiment(experiment_name)
        logger.debug(f"MLflow tracking: {tracking_uri} | experiment: {experiment_name}")
    except Exception as e:
        logger.warning(f"MLflow setup failed (using local): {e}")
        mlflow.set_tracking_uri("./mlruns")
        mlflow.set_experiment(experiment_name)
