"""Unit tests for the API query layer (uses the shared sanitize helper)."""
from app.sanitize import _safe_id, _unsafe_id


def test_safe_id_replaces_slashes_and_dots():
    raw = "gcp://compute/dice-master-the-platform/zone/vm1"
    safe = _safe_id(raw)
    assert "/" not in safe
    # "gcp://" -> "gcp:____" (two slashes -> two "__")
    assert safe == "gcp:____compute__dice-master-the-platform__zone__vm1"


def test_unsafe_id_round_trip_for_slashes():
    raw = "gcp://compute/proj/zone/vm1"
    assert _unsafe_id(_safe_id(raw)) == raw


def test_dashboard_summary_shape():
    # Import lazily so Firestore client isn't constructed at import time.
    from app.queries import dashboard_summary

    # Will hit real Firestore in CI/deploy; here we just assert it returns a dict.
    summary = dashboard_summary()
    assert isinstance(summary, dict)
    for key in (
        "resourceCount",
        "byType",
        "totalMonthlyCostProjection",
        "publicResources",
        "unusedResources",
        "recommendationCount",
        "totalEstimatedSavings",
    ):
        assert key in summary
