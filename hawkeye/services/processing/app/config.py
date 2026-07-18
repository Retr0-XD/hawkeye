"""Configuration for the Hawkeye Processing Service.

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
    service_name: str = "processing"

    # --- Pub/Sub topics (produced by Layer 1) ---------------------------
    pubsub_resources_topic: str = "hawkeye-resources"
    pubsub_metrics_topic: str = "hawkeye-metrics"
    pubsub_billing_topic: str = "hawkeye-billing"
    pubsub_audit_topic: str = "hawkeye-audit"

    # --- Pub/Sub pull subscriptions (owned by this service) -------------
    sub_resources: str = "hawkeye-resources-processing"
    sub_metrics: str = "hawkeye-metrics-processing"
    sub_billing: str = "hawkeye-billing-processing"
    sub_audit: str = "hawkeye-audit-processing"

    # --- Firestore collections ------------------------------------------
    fs_resources: str = "resources"
    fs_costs: str = "costs"
    fs_recommendations: str = "recommendations"
    fs_audit_logs: str = "audit_logs"
    fs_alerts: str = "alerts"
    fs_graph: str = "resource_graph"
    fs_state: str = "processing_state"

    # --- BigQuery tables -------------------------------------------------
    bq_dataset: str = "hawkeye"
    bq_metrics_table: str = "metrics"
    bq_billing_table: str = "billing"
    bq_audit_table: str = "audit_logs"
    bq_lifecycle_table: str = "resource_lifecycle"

    # --- Insight thresholds (architecture: CPU<5%, mem<10% = low util) ---
    low_cpu_threshold: float = 5.0
    low_memory_threshold: float = 10.0
    unused_age_days: int = 30

    # --- Pull behaviour --------------------------------------------------
    pull_max_messages: int = 1000
    pull_timeout: float = 10.0

    # --- Local emulator support -----------------------------------------
    use_emulator: bool = False
    pubsub_emulator_host: str = "localhost:8085"
    firestore_emulator_host: str = "localhost:8080"

    # --- Logging ---------------------------------------------------------
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
