"""GCP client helpers for the ML Service (BigQuery + Firestore)."""
from __future__ import annotations

from functools import lru_cache

from google.cloud import bigquery
from google.cloud import firestore

from .config import Settings, get_settings


@lru_cache
def get_bigquery_client() -> bigquery.Client:
    settings: Settings = get_settings()
    return bigquery.Client(project=settings.gcp_project_id)


@lru_cache
def get_firestore_client() -> firestore.Client:
    settings: Settings = get_settings()
    return firestore.Client(project=settings.gcp_project_id)
