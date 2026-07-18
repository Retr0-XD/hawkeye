"""Configuration for the Hawkeye Automation Service (Week 8)."""
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
    service_name: str = "automation"

    # Firestore collections (must match API / Processing).
    fs_recommendations: str = "recommendations"
    fs_approvals: str = "recommendation_approvals"
    fs_automation_log: str = "automation_log"

    # Safety: automation is opt-in per recommendation via user approval.
    # dry_run=true means we log the intended action but do not execute it.
    dry_run: bool = True

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
