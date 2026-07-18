"""Billing cost reader for Budget Guard.

Reads the project's month-to-date (MTD) cost from the Cloud Billing
API. This is the single source of truth for the free-zone check.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, UTC
from typing import Optional

from googleapiclient import discovery
from google.auth import default

from .config import Settings, get_settings

logger = logging.getLogger("hawkeye.budget-guard.billing")


def _billing_service():
    creds, _ = default()
    return discovery.build("cloudbilling", "v1", credentials=creds, cache_discovery=False)


def get_billing_account_id(settings: Settings | None = None) -> Optional[str]:
    """Resolve the billing account linked to the project."""
    settings = settings or get_settings()
    svc = _billing_service()
    name = f"projects/{settings.gcp_project_id}"
    try:
        info = svc.projects().getBillingInfo(name=name).execute()
        return info.get("billingAccountName", "").split("/")[-1] or None
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read billing account: %s", exc)
        return None


def get_month_to_date_cost(settings: Settings | None = None) -> float:
    """Return the project's month-to-date cost in USD."""
    settings = settings or get_settings()
    acct = get_billing_account_id(settings)
    if not acct:
        logger.warning("No billing account found; assuming $0 MTD.")
        return 0.0
    svc = _billing_service()
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    body = {
        "filter": f'project.id="{settings.gcp_project_id}"',
        "interval": {
            "startTime": start.isoformat(),
            "endTime": now.isoformat(),
        },
    }
    try:
        resp = svc.projects().billingAccounts().costs().query(
            name=f"billingAccounts/{acct}", body=body
        ).execute()
        total = 0.0
        for grp in resp.get("results", []):
            for period in grp.get("valuesPerPeriod", []):
                total += float(period.get("value", 0.0))
        return total
    except Exception as exc:  # noqa: BLE001
        logger.error("Cost query failed: %s", exc)
        return 0.0


def is_over_cap(settings: Settings | None = None) -> tuple[bool, float]:
    settings = settings or get_settings()
    cost = get_month_to_date_cost(settings)
    return cost > settings.monthly_cost_cap_usd, cost
