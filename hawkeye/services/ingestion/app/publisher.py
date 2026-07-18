"""Pub/Sub publisher (Layer 1, operation 5).

Publishes normalized records to the four topics defined in the architecture:
  - hawkeye-resources
  - hawkeye-metrics
  - hawkeye-billing
  - hawkeye-audit
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from .config import Settings, get_settings
from .gcp_clients import get_pubsub_publisher

logger = logging.getLogger("hawkeye.ingestion.publisher")


class Publisher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = get_pubsub_publisher()
        self._topics = {
            "resources": self.settings.pubsub_resources_topic,
            "metrics": self.settings.pubsub_metrics_topic,
            "billing": self.settings.pubsub_billing_topic,
            "audit": self.settings.pubsub_audit_topic,
        }
        self._futures: List[Any] = []

    def _topic_path(self, topic: str) -> str:
        return self._client.topic_path(self.settings.gcp_project_id, self._topics[topic])

    def publish(self, kind: str, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        path = self._topic_path(kind)
        count = 0
        for rec in records:
            data = json.dumps(rec, default=str).encode("utf-8")
            fut = self._client.publish(path, data)
            self._futures.append(fut)
            count += 1
        logger.info("Published %d %s records to %s", count, kind, path)
        return count

    def flush(self) -> None:
        """Block until all pending publishes are acknowledged.

        Raises if any publish failed so the orchestrator does not report a
        successful cycle (and persist last_sync) when messages were lost.
        """
        from concurrent.futures import wait

        if self._futures:
            done, _ = wait(self._futures)
            self._futures.clear()
            errors = [f.exception() for f in done if f.exception()]
            if errors:
                raise RuntimeError(
                    f"{len(errors)} Pub/Sub publish failure(s): {errors[:3]}"
                )
