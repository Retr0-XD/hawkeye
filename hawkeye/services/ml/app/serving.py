"""Model serving: caching + monitoring for ML predictions."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from .config import Settings, get_settings
from .explain import explain_prediction
from .features import invalidate_feature_cache
from .models import predict_resource, train_anomaly_detector, train_failure_predictor

logger = logging.getLogger("hawkeye.ml.serving")

# In-memory cache: resource_id -> (timestamp, prediction)
_cache: Dict[str, tuple] = {}
# Prediction log for monitoring (last N predictions).
_recent: list = []


def _cache_valid(resource_id: str, ttl: int) -> Optional[dict]:
    if resource_id in _cache:
        ts, pred = _cache[resource_id]
        if (datetime.now(timezone.utc) - ts).total_seconds() < ttl:
            return pred
    return None


def predict_cached(resource_id: str) -> dict:
    """Return a cached or fresh prediction for a resource."""
    settings: Settings = get_settings()
    cached = _cache_valid(resource_id, settings.prediction_cache_ttl_seconds)
    if cached is not None:
        return {**cached, "cached": True}

    start = time.time()
    pred = predict_resource(resource_id)
    elapsed = time.time() - start

    if pred.get("predictable"):
        _cache[resource_id] = (datetime.now(timezone.utc), pred)
        _recent.append(
            {
                "resource_id": resource_id,
                "anomaly": pred["anomaly"]["is_anomaly"],
                "failure_risk": pred["failure"]["is_high_risk"],
                "latency_ms": round(elapsed * 1000, 1),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(_recent) > 100:
            _recent.pop(0)
        # Attach explainability (drivers + reason + blended risk score).
        pred["explanation"] = explain_prediction(
            resource_id,
            pred["anomaly"]["score"],
            pred["anomaly"]["is_anomaly"],
            pred["failure"]["probability"],
            pred["failure"]["is_high_risk"],
            pred.get("features", {}) or {},
        )
    return {**pred, "cached": False, "latency_ms": round(elapsed * 1000, 1)}


def retrain() -> dict:
    """Retrain all models from current BigQuery history."""
    anomaly = train_anomaly_detector()
    failure = train_failure_predictor()
    invalidate_feature_cache()
    # Also drop the per-resource prediction cache so the next /predict/all
    # reflects the new models (and any metadata/explanation changes).
    _cache.clear()
    return {
        "anomaly_trained": anomaly is not None,
        "failure_trained": failure is not None,
        "retrained_at": datetime.now(timezone.utc).isoformat(),
    }


def monitoring_summary() -> dict:
    """Aggregate monitoring stats for the model dashboard."""
    if not _recent:
        return {"predictions": 0, "avg_latency_ms": 0.0, "anomalies": 0, "failures": 0}
    lat = [r["latency_ms"] for r in _recent]
    return {
        "predictions": len(_recent),
        "avg_latency_ms": round(sum(lat) / len(lat), 1),
        "anomalies": sum(1 for r in _recent if r["anomaly"]),
        "failures": sum(1 for r in _recent if r["failure_risk"]),
        "last": _recent[-1],
    }
