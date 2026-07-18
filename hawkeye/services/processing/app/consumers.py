"""Pub/Sub pull consumers (Layer 2, operation 1).

Uses explicit synchronous ``pull`` + ``acknowledge`` so a scheduled batch job
has full control over the ACK window: messages are only ACKed after the
orchestrator has persisted them. At-least-once delivery is preserved because a
crash before ACK simply redelivers the same messages (processing is idempotent
on stable document/row keys).
"""
from __future__ import annotations

import json
import logging
from typing import List, Tuple

from .config import Settings, get_settings
from .gcp_clients import get_subscriber
from .models import AuditEvent, BillingRecord, MetricRecord, Resource

logger = logging.getLogger("hawkeye.processing.consumers")

# A "message" envelope: (pubsub_message, parsed_model_or_None)
MessageEnvelope = Tuple[object, object]


def _pull(topic_key: str) -> List[MessageEnvelope]:
    """Pull a bounded batch from the subscription for ``topic_key``."""
    settings = get_settings()
    sub_name = {
        "resources": settings.sub_resources,
        "metrics": settings.sub_metrics,
        "billing": settings.sub_billing,
        "audit": settings.sub_audit,
    }[topic_key]
    subscriber = get_subscriber()
    sub_path = subscriber.subscription_path(settings.gcp_project_id, sub_name)

    resp = subscriber.pull(
        request={
            "subscription": sub_path,
            "max_messages": settings.pull_max_messages,
            "return_immediately": True,
        },
        timeout=settings.pull_timeout + 5,
    )
    envelopes: List[MessageEnvelope] = []
    for msg in resp.received_messages:
        try:
            data = json.loads(msg.message.data.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unparseable message on %s, acking: %s", sub_name, exc)
            subscriber.acknowledge(
                request={"subscription": sub_path, "ack_ids": [msg.ack_id]}
            )
            continue
        envelopes.append((msg, data))
    return envelopes


def _parse(envelopes: List[MessageEnvelope], model):
    out: List[object] = []
    for msg, data in envelopes:
        try:
            out.append(model(**data))
        except Exception as exc:  # noqa: BLE001
            logger.warning("bad %s message: %s", model.__name__, exc)
    return out


def _ack(envelopes: List[MessageEnvelope], topic_key: str) -> None:
    settings = get_settings()
    sub_name = {
        "resources": settings.sub_resources,
        "metrics": settings.sub_metrics,
        "billing": settings.sub_billing,
        "audit": settings.sub_audit,
    }[topic_key]
    subscriber = get_subscriber()
    sub_path = subscriber.subscription_path(settings.gcp_project_id, sub_name)
    ack_ids = [msg.ack_id for msg, _ in envelopes]
    if ack_ids:
        subscriber.acknowledge(request={"subscription": sub_path, "ack_ids": ack_ids})


def pull_resources() -> List[MessageEnvelope]:
    return _pull("resources")


def pull_metrics() -> List[MessageEnvelope]:
    return _pull("metrics")


def pull_billing() -> List[MessageEnvelope]:
    return _pull("billing")


def pull_audit() -> List[MessageEnvelope]:
    return _pull("audit")


def parse_resources(envelopes: List[MessageEnvelope]) -> List[Resource]:
    return _parse(envelopes, Resource)


def parse_metrics(envelopes: List[MessageEnvelope]) -> List[MetricRecord]:
    return _parse(envelopes, MetricRecord)


def parse_billing(envelopes: List[MessageEnvelope]) -> List[BillingRecord]:
    return _parse(envelopes, BillingRecord)


def parse_audit(envelopes: List[MessageEnvelope]) -> List[AuditEvent]:
    return _parse(envelopes, AuditEvent)


def ack_all(resources, metrics, billing, audit) -> None:
    """ACK every pulled message after successful persistence."""
    _ack(resources, "resources")
    _ack(metrics, "metrics")
    _ack(billing, "billing")
    _ack(audit, "audit")
