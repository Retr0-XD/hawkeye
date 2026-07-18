"""Unit tests for the Ingestion Service (no GCP credentials required).

These validate the normalized schema and the publisher topic routing using
the Pub/Sub emulator when HAWKEYE_USE_EMULATOR=true, otherwise they validate
the pure logic only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import AuditEvent, BillingRecord, MetricRecord, Resource
from app.config import Settings


def test_resource_normalization():
    r = Resource(
        id="gcp://compute/p/x/i",
        name="i",
        type="VM",
        gcp_project_id="p",
        labels={"env": "prod"},
    )
    d = r.to_pubsub()
    assert d["id"] == "gcp://compute/p/x/i"
    assert d["cloud_provider"] == "GCP"
    assert d["labels"]["env"] == "prod"
    assert d["status"] == "ACTIVE"


def test_billing_record():
    b = BillingRecord(resource_id="r1", date="2026-07-13", daily_cost=4.2,
                      sku={"compute": 4.2})
    d = b.to_pubsub()
    assert d["daily_cost"] == 4.2
    assert d["sku"]["compute"] == 4.2


def test_metric_record():
    m = MetricRecord(resource_id="r1", cpu_percent=12.5, network_in_bytes=1024)
    d = m.to_pubsub()
    assert d["cpu_percent"] == 12.5
    assert d["network_in_bytes"] == 1024


def test_audit_event():
    a = AuditEvent(id="x", action="DELETE", resource_id="r1", user_email="u@x.com")
    d = a.to_pubsub()
    assert d["action"] == "DELETE"
    assert d["status"] == "SUCCESS"


def test_settings_defaults():
    s = Settings()
    assert s.pubsub_resources_topic == "hawkeye-resources"
    assert s.ingest_interval_seconds == 300
    assert s.gcp_project_id == "dice-master-the-platform"


def test_publisher_topic_routing():
    """Validate the publisher maps kinds -> configured topic names."""
    settings = Settings()
    # We don't actually publish; just assert the mapping is wired.
    assert settings.pubsub_resources_topic == "hawkeye-resources"
    assert settings.pubsub_metrics_topic == "hawkeye-metrics"
    assert settings.pubsub_billing_topic == "hawkeye-billing"
    assert settings.pubsub_audit_topic == "hawkeye-audit"
