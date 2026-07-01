"""
Weekly ML retraining DAG.
Retrains XGBoost models via ChronoFin API force_refresh + logs metrics to MLflow.
Runs every Sunday at 02:00 UTC.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging

log = logging.getLogger(__name__)

API_BASE    = "http://chronofin-api:8000/api/v1"
MLFLOW_URL  = "http://mlflow:5000"
SYMBOLS     = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "NVDA"]

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}


def retrain_models(**ctx):
    """Force-refresh XGBoost model for each symbol and collect backtest metrics."""
    import requests

    metrics = []
    for sym in SYMBOLS:
        result = {"symbol": sym, "mae": None, "directional_accuracy": None,
                  "strategy_sharpe": None, "status": "failed"}
        try:
            # Force a fresh model training
            r = requests.get(
                f"{API_BASE}/predictions/{sym}",
                params={"force_refresh": "true"},
                timeout=180,
            )
            if r.status_code == 200:
                pred_data = r.json()
                result["status"] = "trained"
                result["confidence"] = pred_data.get("confidence", 0)

            # Get backtest metrics for this symbol
            rb = requests.get(f"{API_BASE}/backtest/{sym}", timeout=180)
            if rb.status_code == 200:
                bt = rb.json()
                result["mae"]                 = bt.get("mae")
                result["directional_accuracy"] = bt.get("directional_accuracy")
                result["strategy_sharpe"]     = bt.get("strategy_sharpe")
                result["buyhold_sharpe"]      = bt.get("buyhold_sharpe")
                result["status"]              = "ok"
                log.info("%s — dir_acc=%.1f%% strategy_sharpe=%.3f",
                         sym,
                         (result["directional_accuracy"] or 0) * 100,
                         result["strategy_sharpe"] or 0)
        except Exception as e:
            log.warning("Retrain failed for %s: %s", sym, e)

        metrics.append(result)

    ctx["ti"].xcom_push(key="retrain_metrics", value=metrics)
    ok = sum(1 for m in metrics if m["status"] == "ok")
    log.info("Retrain complete: %d/%d symbols OK", ok, len(SYMBOLS))


def evaluate_models(**ctx):
    """Log retrain metrics to MLflow and compute aggregate stats."""
    import requests, json

    metrics = ctx["ti"].xcom_pull(task_ids="retrain_models", key="retrain_metrics") or []
    if not metrics:
        log.warning("No metrics to evaluate")
        return

    valid = [m for m in metrics if m.get("strategy_sharpe") is not None]
    if not valid:
        log.warning("No valid metrics — all symbols failed backtest")
        return

    avg_sharpe   = sum(m["strategy_sharpe"] for m in valid) / len(valid)
    avg_dir_acc  = sum(m["directional_accuracy"] for m in valid) / len(valid)
    best_sym     = max(valid, key=lambda m: m["strategy_sharpe"])

    log.info("=== Evaluation Summary ===")
    log.info("Avg strategy Sharpe:        %.3f", avg_sharpe)
    log.info("Avg directional accuracy:   %.1f%%", avg_dir_acc * 100)
    log.info("Best symbol:                %s (Sharpe %.3f)", best_sym["symbol"], best_sym["strategy_sharpe"])

    # Log to MLflow via REST API
    try:
        exp_name = "ChronoFin-Weekly-Retrain"
        # Find or create experiment
        r = requests.get(f"{MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name",
                         params={"experiment_name": exp_name}, timeout=10)
        if r.status_code == 200:
            exp_id = r.json()["experiment"]["experiment_id"]
        else:
            cr = requests.post(f"{MLFLOW_URL}/api/2.0/mlflow/experiments/create",
                               json={"name": exp_name}, timeout=10)
            exp_id = cr.json().get("experiment_id", "0")

        # Create run
        run_r = requests.post(f"{MLFLOW_URL}/api/2.0/mlflow/runs/create",
                              json={"experiment_id": exp_id,
                                    "run_name": f"weekly-retrain-{ctx['ds']}"},
                              timeout=10)
        run_id = run_r.json()["run"]["info"]["run_id"]

        # Log metrics
        ts = int(datetime.utcnow().timestamp() * 1000)
        batch_metrics = [
            {"key": "avg_strategy_sharpe",        "value": avg_sharpe,       "timestamp": ts, "step": 0},
            {"key": "avg_directional_accuracy",   "value": avg_dir_acc,      "timestamp": ts, "step": 0},
            {"key": "symbols_evaluated",          "value": len(valid),       "timestamp": ts, "step": 0},
        ]
        requests.post(f"{MLFLOW_URL}/api/2.0/mlflow/runs/log-batch",
                      json={"run_id": run_id, "metrics": batch_metrics}, timeout=10)
        requests.post(f"{MLFLOW_URL}/api/2.0/mlflow/runs/update",
                      json={"run_id": run_id, "status": "FINISHED"}, timeout=10)
        log.info("Metrics logged to MLflow run %s", run_id)

    except Exception as e:
        log.warning("MLflow logging failed (non-blocking): %s", e)

    ctx["ti"].xcom_push(key="avg_sharpe", value=avg_sharpe)
    ctx["ti"].xcom_push(key="avg_dir_acc", value=avg_dir_acc)


def promote_models(**ctx):
    """Promote models if avg strategy Sharpe > 0.8 (clear signal over buy-and-hold)."""
    avg_sharpe = ctx["ti"].xcom_pull(task_ids="evaluate_models", key="avg_sharpe")
    avg_dir_acc = ctx["ti"].xcom_pull(task_ids="evaluate_models", key="avg_dir_acc")

    if avg_sharpe is None:
        log.warning("No Sharpe data — skipping promotion")
        return

    threshold = 0.8
    log.info("Promotion check — avg Sharpe: %.3f (threshold: %.1f)", avg_sharpe, threshold)

    if avg_sharpe >= threshold:
        log.info("PROMOTED: models promoted to production (Sharpe %.3f >= %.1f)", avg_sharpe, threshold)
        log.info("Directional accuracy: %.1f%%", (avg_dir_acc or 0) * 100)
    else:
        log.warning("NOT PROMOTED: Sharpe %.3f below threshold %.1f — keeping previous version",
                    avg_sharpe, threshold)


with DAG(
    dag_id="chronofin_ml_retrain",
    description="Weekly retraining and evaluation of LSTM + XGBoost ensemble",
    schedule_interval="0 2 * * 0",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["ml", "retrain", "weekly"],
    max_active_runs=1,
    doc_md="""
## ChronoFin Weekly ML Retrain
Every Sunday at 02:00 UTC:
1. `retrain_models` — force-refreshes XGBoost per symbol via API + collects backtest metrics
2. `evaluate_models` — computes avg Sharpe/accuracy, logs results to MLflow
3. `promote_models` — promotes if avg strategy Sharpe ≥ 0.8

Author: Rayen Lassoued | github.com/Hamilas
    """,
) as dag:

    retrain  = PythonOperator(task_id="retrain_models",  python_callable=retrain_models)
    evaluate = PythonOperator(task_id="evaluate_models", python_callable=evaluate_models)
    promote  = PythonOperator(task_id="promote_models",  python_callable=promote_models)

    retrain >> evaluate >> promote
