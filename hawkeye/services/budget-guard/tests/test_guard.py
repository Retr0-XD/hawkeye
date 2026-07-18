"""Unit tests for Budget Guard (pure logic, no GCP creds needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.guard import _month_key


def test_settings_defaults():
    s = Settings()
    assert s.monthly_cost_cap_usd == 0.10
    assert s.gcp_project_id == "dice-master-the-platform"
    from app.guard import GUARDED_SERVICES

    # All deployed billable Cloud Run services must be guarded.
    for svc in [
        "aether", "apollo", "athena", "atlas", "cost-guard",
        "dashboard", "lattice", "odin", "orion",
        "hawkeye-ingestion", "hawkeye-processing", "hawkeye-api", "budget-guard",
    ]:
        assert svc in GUARDED_SERVICES, f"{svc} missing from GUARDED_SERVICES"


def test_month_key_format():
    # YYYY-MM, stable within a month.
    k1 = _month_key()
    assert len(k1) == 7
    assert k1[4] == "-"
    assert k1 == _month_key()


def test_orchestrator_runs():
    # run_guard touches GCP; just ensure it imports and is callable.
    from app.orchestrator import run_guard

    # We don't call it (needs creds); verify signature via getattr.
    assert callable(run_guard)
