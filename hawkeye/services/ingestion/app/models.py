"""Normalized data models (the common schema from the architecture doc).

These mirror the Firestore ``/resources``, ``/metrics``, ``/costs`` and
``/audit_logs`` collections so that downstream services can consume a single
stable shape regardless of which GCP API produced the raw data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resource(BaseModel):
    """Normalized cloud resource (Firestore ``/resources/{id}``)."""

    id: str
    name: str
    type: str  # VM, Database, Storage, Network, Container, Function, Cluster
    cloud_provider: str = "GCP"
    provider_id: Optional[str] = None  # numeric/provider-native id (e.g. GCE instance id)
    gcp_project_id: str
    region: Optional[str] = None
    zone: Optional[str] = None
    status: str = "ACTIVE"  # ACTIVE, STOPPED, DELETED
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None
    owner_email: Optional[str] = None
    team_id: Optional[str] = None
    parent_resources: List[str] = Field(default_factory=list)
    child_resources: List[str] = Field(default_factory=list)
    last_cost_update: Optional[datetime] = None
    monthly_cost_projection: float = 0.0
    cost_trend: str = "STABLE"  # UP, STABLE, DOWN
    last_metric_update: Optional[datetime] = None
    cpu_utilization_avg: Optional[float] = None
    memory_utilization_avg: Optional[float] = None
    network_egress_gb: Optional[float] = None
    encryption_status: Optional[str] = None  # ENCRYPTED, UNENCRYPTED
    public_access: bool = False
    backup_enabled: Optional[bool] = None
    audit_logging_enabled: Optional[bool] = None
    last_accessed: Optional[datetime] = None
    pending_recommendations: List[str] = Field(default_factory=list)
    optimization_potential_dollars: float = 0.0

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class MetricRecord(BaseModel):
    """Normalized usage metric sample (Firestore ``/metrics`` + BQ ``metrics``)."""

    resource_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    cpu_percent: Optional[float] = None
    cpu_percent_avg: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_iops: Optional[float] = None
    network_in_bytes: Optional[int] = None
    network_out_bytes: Optional[int] = None
    queries_per_second: Optional[float] = None
    active_connections: Optional[int] = None
    replication_lag_ms: Optional[float] = None
    error_rate_percent: Optional[float] = None
    error_count: Optional[int] = None
    uptime_percent: Optional[float] = None
    incidents_count: Optional[int] = None

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class BillingRecord(BaseModel):
    """Normalized daily cost (Firestore ``/costs/{id}/{date}`` + BQ ``billing``)."""

    resource_id: str
    date: str  # YYYY-MM-DD
    daily_cost: float = 0.0
    sku: Dict[str, float] = Field(default_factory=dict)
    month_to_date: float = 0.0
    cost_change_percent: float = 0.0
    anomaly_score: float = 0.0

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class AuditEvent(BaseModel):
    """Normalized audit event (Firestore ``/audit_logs`` + BQ ``audit_logs``)."""

    id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    user_email: Optional[str] = None
    user_ip: Optional[str] = None
    action: str  # CREATE, UPDATE, DELETE, APPROVE, EXECUTE
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    changes: Dict[str, Any] = Field(default_factory=dict)
    status: str = "SUCCESS"  # SUCCESS, FAILURE
    error_message: Optional[str] = None

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")
