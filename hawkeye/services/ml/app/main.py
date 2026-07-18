"""FastAPI entry point for the Hawkeye ML / Prediction Service.

Endpoints:
  - GET  /livez                  liveness probe
  - GET  /                       service info
  - POST /ml/predict/{id}        predict anomaly/failure/cost for one resource
  - POST /ml/predict/all         predict for all resources in Firestore
  - POST /ml/retrain             retrain models from BigQuery history
  - GET  /ml/monitoring          model monitoring summary
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import get_settings
from .gcp_clients import get_firestore_client
from .serving import monitoring_summary, predict_cached, retrain

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("hawkeye.ml.main")

app = FastAPI(title="Hawkeye ML Service", version="0.1.0")


@app.on_event("startup")
async def _ensure_models():
    """Train models on cold start if none are persisted yet.

    Cloud Run's ephemeral disk loses trained models on every scale-to-0 ->
    cold-start cycle. Without this, the service would serve untrained (all
    neutral) predictions until someone manually called /ml/retrain. We train
    lazily at startup only if a model file is missing, and never block startup
    if BigQuery has no data yet (training logs a warning and returns None).
    """
    try:
        from .models import (
            load_anomaly_detector,
            load_failure_predictor,
            train_anomaly_detector,
            train_failure_predictor,
        )

        if load_anomaly_detector() is None:
            train_anomaly_detector()
        if load_failure_predictor() is None:
            train_failure_predictor()
        logger.info("ML model warmup complete")
    except Exception as exc:  # noqa: BLE001
        logger.warning("ML model warmup skipped (will retry on /ml/retrain): %s", exc)


@app.get("/livez")
async def livez():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "hawkeye-ml", "status": "running"}


@app.post("/ml/predict/all")
async def predict_all():
    settings = get_settings()
    db = get_firestore_client()
    docs = list(db.collection("resources").stream())
    results = []
    for d in docs:
        # Use the raw resource id (matches BigQuery resource_id), not the
        # sanitized Firestore document id.
        rid = d.to_dict().get("id", d.id)
        pred = predict_cached(rid)
        if pred.get("predictable"):
            results.append(pred)
    # Rank by blended explainable risk score so the UI can show "top risks".
    results.sort(
        key=lambda r: (r.get("explanation", {}) or {}).get("risk_score", 0.0),
        reverse=True,
    )
    high = [r["resource_id"] for r in results if (r.get("explanation", {}) or {}).get("risk_level") == "HIGH"]
    return JSONResponse(
        content={
            "scored": len(results),
            "total_resources": len(docs),
            "anomalies": [r["resource_id"] for r in results if r["anomaly"]["is_anomaly"]],
            "failure_risks": [
                r["resource_id"] for r in results if r["failure"]["is_high_risk"]
            ],
            "high_risk": high,
            "items": results,
        }
    )


@app.post("/ml/predict/{resource_id:path}")
async def predict_one(resource_id: str):
    result = predict_cached(resource_id)
    if not result.get("predictable", False):
        raise HTTPException(
            status_code=404,
            detail="no metrics/cost history for this resource to predict on",
        )
    return JSONResponse(content=result)


@app.post("/ml/retrain")
async def retrain_models():
    return JSONResponse(content=retrain())


@app.get("/ml/monitoring")
async def monitoring():
    return JSONResponse(content=monitoring_summary())
