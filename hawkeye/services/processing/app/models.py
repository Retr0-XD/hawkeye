"""Normalized data models — mirror the ingestion service schema.

Kept in sync with ``ingestion/app/models.py`` so the two services can evolve
independently while still speaking the same Pub/Sub contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resource(BaseModel):
    id: str
    name: str
    type: str
    cloud_provider: str = "GCP"
    provider_id: Optional[str] = None
    gcp_project_id: str
    region: Optional[str] = None
    zone: Optional[str] = None
    status: str = "ACTIVE"
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
    cost_trend: str = "STABLE"
    last_metric_update: Optional[datetime] = None
    cpu_utilization_avg: Optional[float] = None
    memory_utilization_avg: Optional[float] = None
    network_egress_gb: Optional[float] = None
    encryption_status: Optional[str] = None
    public_access: bool = False
    backup_enabled: Optional[bool] = None
    audit_logging_enabled: Optional[bool] = None
    last_accessed: Optional[datetime] = None
    pending_recommendations: List[str] = Field(default_factory=list)
    optimization_potential_dollars: float = 0.0

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class MetricRecord(BaseModel):
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
    resource_id: str
    date: str
    daily_cost: float = 0.0
    sku: Dict[str, float] = Field(default_factory=dict)
    month_to_date: float = 0.0
    cost_change_percent: float = 0.0
    anomaly_score: float = 0.0

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class AuditEvent(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    user_email: Optional[str] = None
    user_ip: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    changes: Dict[str, Any] = Field(default_factory=dict)
    status: str = "SUCCESS"
    error_message: Optional[str] = None

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class Recommendation(BaseModel):
    id: str
    type: str  # COST, SECURITY, PERFORMANCE
    resource_id: str
    title: str
    description: str
    estimated_savings: float = 0.0
    severity: str = "LOW"  # LOW, MEDIUM, HIGH
    status: str = "PENDING"  # PENDING, APPROVED, APPLIED, REJECTED
    created_at: datetime = Field(default_factory=_utcnow)
    confidence: float = 0.0

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class Alert(BaseModel):
    id: str
    name: str
    type: str  # COST_SPIKE, UNUSED_RESOURCE, SECURITY_VIOLATION, SLO_BREACH, LIFECYCLE_CHANGE
    resource_id: Optional[str] = None
    condition: str
    severity: str = "LOW"  # LOW, MEDIUM, HIGH
    enabled: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_pubsub(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")
