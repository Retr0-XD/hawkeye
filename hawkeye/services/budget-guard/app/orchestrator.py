"""Budget Guard orchestrator: the free-forever decision loop.

Logic (idempotent, safe to run every minute):
  1. Read month-to-date cost.
  2. If cost > cap AND not already suspended this month -> suspend + record.
  3. If a new month has started AND we were suspended -> resume + record.
  4. Otherwise -> no-op (stay in free zone).
"""
from __future__ import annotations

import logging

from .billing import get_month_to_date_cost, is_over_cap
from .config import Settings, get_settings
from .guard import (
    _month_key,
    get_state,
    resume_all,
    set_state,
    suspend_all,
)

logger = logging.getLogger("hawkeye.budget-guard.orchestrator")


def run_guard() -> dict:
    settings = get_settings()
    over, cost = is_over_cap(settings)
    state = get_state(settings)
    suspended = state.get("suspended", False)
    suspended_month = state.get("suspended_month")
    current_month = _month_key()

    result = {
        "cost_mtd_usd": round(cost, 4),
        "cap_usd": settings.monthly_cost_cap_usd,
        "over_cap": over,
        "action": "none",
    }

    if over and not (suspended and suspended_month == current_month):
        # New breach this month -> suspend once.
        actions = suspend_all(settings)
        set_state(suspended=True, cost=cost, settings=settings)
        result["action"] = "suspended"
        result["actions"] = actions
        logger.warning("OVER CAP: suspended all services. cost=$%.4f", cost)

    elif suspended and suspended_month != current_month:
        # New month rolled over -> resume.
        actions = resume_all(settings)
        set_state(suspended=False, cost=cost, settings=settings)
        result["action"] = "resumed"
        result["actions"] = actions
        logger.info("NEW MONTH: resumed all services. cost=$%.4f", cost)

    else:
        result["action"] = "none"
        logger.info("Within free zone. cost=$%.4f cap=$%.2f", cost, settings.monthly_cost_cap_usd)

    return result
