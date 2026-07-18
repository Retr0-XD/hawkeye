"""Lazy GCP client factories for the Automation Service."""
from __future__ import annotations

from functools import lru_cache

from .config import Settings, get_settings


@lru_cache
def get_firestore_client():
    from google.cloud import firestore

    return firestore.Client(project=get_settings().gcp_project_id)


@lru_cache
def get_run_admin_client():
    from google.cloud import run_v2

    return run_v2.ServicesClient()
