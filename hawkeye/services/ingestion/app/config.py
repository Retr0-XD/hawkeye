"""Configuration for the Hawkeye Ingestion Service.

All values can be overridden via environment variables prefixed with
``HAWKEYE_`` (e.g. ``HAWKEYE_GCP_PROJECT_ID``) or a local ``.env`` file.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HAWKEYE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core identity ---------------------------------------------------
    gcp_project_id: str = "dice-master-the-platform"
    service_name: str = "ingestion"

    # --- Pub/Sub topics (Layer 1 publishes to these) --------------------
    pubsub_resources_topic: str = "hawkeye-resources"
    pubsub_metrics_topic: str = "hawkeye-metrics"
    pubsub_billing_topic: str = "hawkeye-billing"
    pubsub_audit_topic: str = "hawkeye-audit"

    # --- Firestore state -------------------------------------------------
    firestore_state_collection: str = "ingestion_state"
    firestore_state_doc: str = "last_sync"

    # --- BigQuery exports (billing + audit) -----------------------------
    # These are populated from the Cloud Billing Export -> BigQuery and
    # Cloud Audit Logs -> BigQuery exports. Left empty => collector skips
    # gracefully and logs a warning (no stub, just optional).
    billing_bq_dataset: str = ""
    billing_bq_table: str = ""
    audit_bq_dataset: str = ""
    audit_bq_table: str = ""

    # --- Scheduling ------------------------------------------------------
    ingest_interval_seconds: int = 300  # 5 minutes per the architecture doc
    ingest_on_startup: bool = False  # triggered by ingestion-tick scheduler

    # --- Local emulator support -----------------------------------------
    use_emulator: bool = False
    pubsub_emulator_host: str = "localhost:8085"
    firestore_emulator_host: str = "localhost:8080"

    # --- Logging ---------------------------------------------------------
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
