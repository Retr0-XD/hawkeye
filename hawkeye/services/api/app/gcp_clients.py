"""Lazy GCP client factories for the API Service."""
from __future__ import annotations

import os
from functools import lru_cache

from .config import Settings, get_settings


def _apply_emulator_env(settings: Settings) -> None:
    if settings.use_emulator:
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host
        os.environ["PUBSUB_EMULATOR_HOST"] = settings.pubsub_emulator_host


@lru_cache
def get_firestore_client():
    from google.cloud import firestore

    _apply_emulator_env(get_settings())
    return firestore.Client(project=get_settings().gcp_project_id)


@lru_cache
def get_bigquery_client():
    from google.cloud import bigquery

    return bigquery.Client(project=get_settings().gcp_project_id)
