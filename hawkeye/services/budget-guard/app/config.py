"""Configuration for Hawkeye Budget Guard."""
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
    service_name: str = "budget-guard"

    # Hard monthly cap. If month-to-date spend exceeds this, suspend everything.
    monthly_cost_cap_usd: float = 0.10

    # Services that are billable and must be suspended when over cap.
    # Cloud Run services are serverless (scale-to-0) and free at idle, but we
    # still revoke public access + pause schedulers to be safe.
    region: str = "us-central1"

    # Firestore doc tracking suspension state.
    state_collection: str = "hawkeye_state"
    state_doc: str = "budget_guard"

    # Scheduler job names that should be paused when over cap.
    scheduler_jobs: list[str] = []

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
