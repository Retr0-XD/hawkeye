"""Unit tests for the Processing Service correlation + insight logic."""
from datetime import datetime, timezone

from app.correlate import build_graph, correlate_costs, correlate_metrics, detect_changes_sanitized
from app.insights import generate_recommendations
from app.models import BillingRecord, MetricRecord, Resource


def _res(rid, **kw):
    base = dict(
        id=rid, name=rid, type="VM", gcp_project_id="dice-master-the-platform",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    base.update(kw)
    return Resource(**base)


def test_correlate_costs_attaches_projection():
    res = {r.id: r for r in [_res("gcp://compute/p/z/vm1")]}
    billing = [BillingRecord(resource_id="gcp://compute/p/z/vm1", date="2026-07-13",
                             daily_cost=0.5, month_to_date=15.0, cost_change_percent=12.0)]
    out = correlate_costs(res, billing)
    assert out["gcp://compute/p/z/vm1"].monthly_cost_projection == 15.0
    assert out["gcp://compute/p/z/vm1"].cost_trend == "UP"


def test_correlate_metrics_rolls_up():
    res = {r.id: r for r in [_res("gcp://compute/p/z/vm2")]}
    metrics = [MetricRecord(resource_id="gcp://compute/p/z/vm2", cpu_percent_avg=3.0,
                            memory_percent=8.0, network_out_bytes=1024 ** 3)]
    out = correlate_metrics(res, metrics)
    r = out["gcp://compute/p/z/vm2"]
    assert r.cpu_utilization_avg == 3.0
    assert r.memory_utilization_avg == 8.0
    assert r.network_egress_gb == 1.0


def test_build_graph_explicit_and_implicit():
    res = {r.id: r for r in [
        _res("gcp://lb", type="Network", child_resources=["gcp://vm"]),
        _res("gcp://vm", type="VM"),
    ]}
    graph = build_graph(res, [])
    assert "gcp://vm" in graph["gcp://lb"]
    assert graph["gcp://vm"] == []


def test_detect_changes_new_only():
    from app.storage import _safe_id
    current = {_safe_id(r.id) for r in [_res("gcp://a"), _res("gcp://b")]}
    # Partial-batch semantics: only "new" is flagged; deletions are detected
    # by a separate full-snapshot reconciliation, not per partial batch.
    new, deleted, modified = detect_changes_sanitized(
        current, previous_ids={_safe_id("gcp://a"), _safe_id("gcp://old")}
    )
    assert set(new) == {_safe_id("gcp://b")}
    assert deleted == []


def test_recommendations_unused_high_cost():
    res = {r.id: r for r in [_res(
        "gcp://compute/p/z/oldvm",
        type="VM",
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        monthly_cost_projection=20.0,
        cpu_utilization_avg=1.0,
        memory_utilization_avg=2.0,
    )]}
    recs = generate_recommendations(res)
    assert any(r.type == "COST" and r.severity == "HIGH" for r in recs)
    assert recs[0].estimated_savings > 0


def test_recommendations_public_database_security():
    res = {r.id: r for r in [_res("gcp://sql/db", type="Database", public_access=True)]}
    recs = generate_recommendations(res)
    assert any(r.type == "SECURITY" for r in recs)
