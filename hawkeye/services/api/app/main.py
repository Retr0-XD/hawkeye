"""FastAPI entry point for the Hawkeye API / Query Service.

REST endpoints (mirroring the architecture doc's GraphQL query shapes):
  - GET /livez                      liveness probe
  - GET /                          service info
  - GET /api/resources             list (filter by type/status/public, paginated)
  - GET /api/resources/{id}        resource detail (+ costs/metrics deps)
  - GET /api/recommendations       list (filter by type/severity)
  - GET /api/alerts                list lifecycle/security alerts
  - GET /api/graph                 dependency graph (edges)
  - GET /api/metrics               recent metrics (optionally by resource)
  - GET /api/cost-trend            daily cost trend (if billing export enabled)
  - GET /api/dashboard             aggregate summary for the demo dashboard
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .queries import (
    compliance_summary,
    cost_breakdown,
    cost_trend,
    dashboard_summary,
    get_graph,
    get_resource,
    list_alerts,
    list_recommendations,
    list_resources,
    ml_predictions,
    recent_metrics,
    smart_insights,
)
from .user import router as user_router
from .gcp_user_router import router as gcp_user_router

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("hawkeye.api.main")

app = FastAPI(title="Hawkeye API Service", version="1.0.0")

# CORS: restrict to the known Hawkeye frontend origins. The user console and
# demo are served from Cloud Run; add other origins (Vercel, custom domain) here.
# We deliberately do NOT use "*" so the API is not callable from arbitrary sites.
_ALLOWED_ORIGINS = [
    "https://hawkeye-frontend-demo-78803747777.us-central1.run.app",
    "https://hawkeye-frontend-user-78803747777.us-central1.run.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Week 7: user-facing endpoints (require Google ID token).
app.include_router(user_router)
# Multi-tenant: per-user GCP reads (user's own projects/resources via their token).
app.include_router(gcp_user_router)


@app.get("/livez")
def livez():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "hawkeye-api",
        "status": "running",
        "project": get_settings().gcp_project_id,
    }


@app.get("/api/resources")
def api_resources(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    type: Optional[str] = None,
    status: Optional[str] = None,
    public: bool = False,
):
    return list_resources(limit=limit, offset=offset, resource_type=type, status=status, public_only=public)


@app.get("/api/resources/{resource_id:path}")
def api_resource_detail(resource_id: str):
    res = get_resource(resource_id)
    if res is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return res


@app.get("/api/recommendations")
def api_recommendations(
    limit: int = Query(50, ge=1, le=200),
    type: Optional[str] = None,
    severity: Optional[str] = None,
):
    return list_recommendations(limit=limit, rec_type=type, severity=severity)


@app.get("/api/alerts")
def api_alerts(limit: int = Query(50, ge=1, le=200)):
    return list_alerts(limit=limit)


@app.get("/api/graph")
def api_graph():
    return get_graph()


@app.get("/api/metrics")
def api_metrics(
    resource_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    return {"items": recent_metrics(resource_id, limit=limit)}


@app.get("/api/cost-trend")
def api_cost_trend(days: int = Query(30, ge=1, le=365)):
    return {"items": cost_trend(days=days)}


@app.get("/api/dashboard")
def api_dashboard():
    return dashboard_summary()


@app.get("/api/cost-breakdown")
def api_cost_breakdown():
    return cost_breakdown()


@app.get("/api/compliance")
def api_compliance():
    return compliance_summary()


@app.get("/api/predictions")
def api_predictions():
    return ml_predictions()


@app.get("/api/insights")
def api_insights():
    return smart_insights()
