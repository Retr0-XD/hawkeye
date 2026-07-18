"""Centralized GCP client construction.

Handles emulator environment variables (so the service runs locally against
the Firestore / Pub/Sub emulators with zero cost) and reuses a single client
instance per type. All clients are created lazily so that importing this module
never requires credentials.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from .config import Settings, get_settings

logger = logging.getLogger("hawkeye.ingestion.clients")


def _apply_emulator_env(settings: Settings) -> None:
    if settings.use_emulator:
        os.environ["PUBSUB_EMULATOR_HOST"] = settings.pubsub_emulator_host
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host
        logger.warning(
            "Emulator mode ON: PUBSUB=%s FIRESTORE=%s",
            settings.pubsub_emulator_host,
            settings.firestore_emulator_host,
        )


@lru_cache(maxsize=None)
def get_pubsub_publisher():
    from google.cloud import pubsub_v1

    _apply_emulator_env(get_settings())
    return pubsub_v1.PublisherClient()


@lru_cache(maxsize=None)
def get_firestore_client():
    from google.cloud import firestore

    _apply_emulator_env(get_settings())
    return firestore.Client(project=get_settings().gcp_project_id)


@lru_cache(maxsize=None)
def get_compute_client():
    from google.cloud import compute_v1

    return compute_v1.InstancesClient()


@lru_cache(maxsize=None)
def get_compute_networks_client():
    from google.cloud import compute_v1

    return compute_v1.NetworksClient()


@lru_cache(maxsize=None)
def get_compute_subnetworks_client():
    from google.cloud import compute_v1

    return compute_v1.SubnetworksClient()


@lru_cache(maxsize=None)
def get_compute_forwarding_rules_client():
    from google.cloud import compute_v1

    return compute_v1.ForwardingRulesClient()


@lru_cache(maxsize=None)
def get_storage_client():
    from google.cloud import storage

    return storage.Client(project=get_settings().gcp_project_id)


@lru_cache(maxsize=None)
def get_container_client():
    from google.cloud import container_v1

    return container_v1.ClusterManagerClient()


@lru_cache(maxsize=None)
def get_monitoring_client():
    from google.cloud import monitoring_v3

    return monitoring_v3.MetricServiceClient()


@lru_cache(maxsize=None)
def get_bigquery_client():
    from google.cloud import bigquery

    return bigquery.Client(project=get_settings().gcp_project_id)


@lru_cache(maxsize=None)
def get_discovery_service() -> Optional[object]:
    """Generic Discovery client for APIs without first-class libraries
    (Cloud SQL Admin, Cloud Run Admin, Cloud Functions, Artifact Registry)."""
    try:
        from googleapiclient import discovery
        from google.auth import default

        creds, _ = default()
        return discovery
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to build discovery service: %s", exc)
        return None


def get_discovery_resource(api_name: str, api_version: str, service_obj=None):
    """Build a discovery resource for the given API."""
    if service_obj is None:
        service_obj = get_discovery_service()
    if service_obj is None:
        return None
    from google.auth import default

    creds, _ = default()
    return service_obj.build(api_name, api_version, credentials=creds, cache_discovery=False)
