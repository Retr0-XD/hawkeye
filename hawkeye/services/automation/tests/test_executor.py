"""Smoke tests for the automation executor (no GCP calls)."""
from __future__ import annotations

from app.config import Settings
from app.executor import _action_for_type, _parse_resource


def test_parse_resource_run():
    p = _parse_resource("gcp://run/dice-master-the-platform/aether")
    assert p == {"kind": "run", "project": "dice-master-the-platform", "name": "aether"}


def test_parse_resource_invalid():
    assert _parse_resource("not-a-resource") is None


def test_action_for_type():
    assert _action_for_type("COST") == "optimize_cost"
    assert _action_for_type("SECURITY") == "fix_security"
    assert _action_for_type("PERFORMANCE") == "optimize_performance"
    assert _action_for_type("UNKNOWN") is None


def test_settings_dry_run_default():
    s = Settings()
    assert s.dry_run is True
