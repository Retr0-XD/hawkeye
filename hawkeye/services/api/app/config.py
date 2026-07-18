"""Configuration for the Hawkeye API Service."""
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

    gcp_project_id: str = "dice-master-the-platform"
    service_name: str = "api"

    # Firestore collections (must match processing service).
    fs_resources: str = "resources"
    fs_costs: str = "costs"
    fs_recommendations: str = "recommendations"
    fs_alerts: str = "alerts"
    fs_graph: str = "resource_graph"
    fs_audit_logs: str = "audit_logs"

    # BigQuery.
    bq_dataset: str = "hawkeye"
    bq_metrics_table: str = "metrics"
    bq_billing_table: str = "billing"
    bq_audit_table: str = "audit_logs"

    # Pagination defaults.
    default_page_size: int = 50
    max_page_size: int = 200

    # Local emulator support.
    use_emulator: bool = False
    firestore_emulator_host: str = "localhost:8080"
    pubsub_emulator_host: str = "localhost:8085"

    # ML / Prediction service (Layer 4). Optional; predictions degrade to
    # empty if the service is unreachable.
    ml_service_url: str = (
        "https://hawkeye-ml-78803747777.us-central1.run.app"
    )

    # Week 7: Google OAuth (Google Identity Services ID-token verification).
    # oauth_client_id is the Web client ID from Google Cloud Console. If empty,
    # audience is not checked (token signature + expiry still verified).
    oauth_client_id: str = ""
    # Comma-separated allow-list of emails. Empty = allow any verified Google account.
    allowed_emails: str = ""

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
