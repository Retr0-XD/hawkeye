"""Configuration for the Hawkeye ML Service.

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
    service_name: str = "ml"
    bq_dataset: str = "hawkeye"

    # --- Firestore collections (must match processing / api services) ----
    # Used by the explainability layer to read structural resource metadata.
    fs_resources: str = "resources"

    # --- Model thresholds (from architecture doc) -----------------------
    anomaly_threshold: float = 0.7  # Isolation Forest anomaly score
    failure_threshold: float = 0.7  # failure probability
    cost_spike_ratio: float = 1.5  # predicted/usual cost ratio to flag spike

    # --- Explainability / blended risk thresholds -----------------------
    # Structural risk is blended with the model score to produce a single
    # explainable risk_score in [0, 1]. These cut points map it to levels.
    high_risk_threshold: float = 0.45
    medium_risk_threshold: float = 0.2

    # --- Training --------------------------------------------------------
    training_history_days: int = 30
    min_training_samples: int = 10  # need enough rows to train safely

    # --- Serving ---------------------------------------------------------
    prediction_cache_ttl_seconds: int = 3600  # 1h cache per doc

    # --- Local emulator support -----------------------------------------
    use_emulator: bool = False
    firestore_emulator_host: str = "localhost:8080"

    # --- Logging ---------------------------------------------------------
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
