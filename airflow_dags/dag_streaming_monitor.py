"""
Streaming monitor DAG.
Checks Kafka consumer lag and validates real-time data quality every 5 minutes.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging

log = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 0,
    "email_on_failure": False,
}


def check_kafka_lag(**ctx):
    """Check Kafka consumer lag — report metrics, never fail the pipeline."""
    import os

    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    try:
        from kafka import KafkaConsumer
        from kafka.structs import TopicPartition

        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap,
            group_id="stock_pipeline",
            request_timeout_ms=5000,
            connections_max_idle_ms=8000,
        )
        topic = "stock_prices_raw"
        partitions = consumer.partitions_for_topic(topic) or set()
        if not partitions:
            log.info("Topic '%s' has no partitions yet — Kafka running but no producers", topic)
            consumer.close()
            ctx["ti"].xcom_push(key="kafka_lag", value=0)
            ctx["ti"].xcom_push(key="kafka_status", value="no_topic")
            return

        total_lag = 0
        for p in partitions:
            tp = TopicPartition(topic, p)
            consumer.assign([tp])
            consumer.seek_to_end(tp)
            end_offset = consumer.position(tp)
            consumer.seek_to_beginning(tp)
            begin_offset = consumer.position(tp)
            total_lag += max(0, end_offset - begin_offset)
        consumer.close()

        ctx["ti"].xcom_push(key="kafka_lag", value=total_lag)
        ctx["ti"].xcom_push(key="kafka_status", value="ok")
        log.info("Kafka consumer lag: %d messages (threshold: 10000)", total_lag)

        if total_lag > 10_000:
            log.warning("LAG ALERT: consumer lag %d exceeds threshold 10000", total_lag)

    except Exception as e:
        log.warning("Kafka check skipped (%s: %s) — broker may be warming up", type(e).__name__, e)
        ctx["ti"].xcom_push(key="kafka_lag", value=-1)
        ctx["ti"].xcom_push(key="kafka_status", value=f"unavailable:{type(e).__name__}")


def validate_stream_schema(**ctx):
    """Spot-check live Kafka messages. Never fails — logs quality metrics only."""
    import os, json

    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    kafka_status = ctx["ti"].xcom_pull(task_ids="check_kafka_lag", key="kafka_status") or ""

    if "unavailable" in str(kafka_status):
        log.info("Skipping schema validation — Kafka unavailable (%s)", kafka_status)
        return

    try:
        from kafka import KafkaConsumer

        consumer = KafkaConsumer(
            "stock_prices_raw",
            bootstrap_servers=bootstrap,
            auto_offset_reset="latest",
            consumer_timeout_ms=4000,
            request_timeout_ms=5000,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        required_fields = {"symbol", "price", "volume", "timestamp"}
        errors, checked = 0, 0
        for msg in consumer:
            data = msg.value
            missing = required_fields - set(data.keys())
            if missing:
                log.warning("Missing fields: %s", missing)
                errors += 1
            if data.get("price", 0) <= 0:
                log.warning("Non-positive price: %s", data)
                errors += 1
            checked += 1
            if checked >= 50:
                break
        consumer.close()
        log.info("Stream validation: %d messages checked, %d schema errors", checked, errors)

    except Exception as e:
        log.info("Stream schema check skipped (%s: %s)", type(e).__name__, e)


with DAG(
    dag_id="chronofin_streaming_monitor",
    description="Monitors Kafka consumer lag and validates streaming data quality",
    schedule_interval="*/5 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["streaming", "monitoring"],
    max_active_runs=1,
    doc_md="""
## ChronoFin Streaming Monitor
Checks Kafka consumer lag every 5 minutes.
- Lag > 10,000 messages → WARNING logged (never blocks pipeline)
- Schema validation on latest messages
- Gracefully skips if Kafka broker is warming up
Author: Rayen Lassoued | github.com/Hamilas
    """,
) as dag:

    lag_check = PythonOperator(
        task_id="check_kafka_lag",
        python_callable=check_kafka_lag,
    )
    schema_check = PythonOperator(
        task_id="validate_stream_schema",
        python_callable=validate_stream_schema,
    )

    lag_check >> schema_check
