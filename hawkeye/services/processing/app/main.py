"""FastAPI entry point for the Hawkeye Processing Service.

Endpoints:
  - GET  /livez            liveness probe (Cloud Run reserved /healthz)
  - GET  /                service info
  - POST /process/run     run one processing cycle (also called by scheduler)
  - GET  /process/status  last cycle summary from Firestore
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI

from .config import get_settings
from .gcp_clients import get_firestore_client
from .orchestrator import process_cycle

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("hawkeye.processing.main")

app = FastAPI(title="Hawkeye Processing Service", version="1.0.0")


@app.get("/livez")
def livez() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "hawkeye-processing",
        "status": "running",
        "project": get_settings().gcp_project_id,
    }


@app.post("/process/run")
def run_process() -> Dict[str, Any]:
    summary = process_cycle()
    # Persist last cycle summary for the status endpoint.
    try:
        db = get_firestore_client()
        db.collection(get_settings().fs_state).document("last_cycle").set(
            {**summary, "recorded_at": datetime.now(timezone.utc)}
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not persist last_cycle: %s", exc)
    return summary


@app.get("/process/status")
def process_status() -> Dict[str, Any]:
    try:
        db = get_firestore_client()
        doc = (
            db.collection(get_settings().fs_state)
            .document("last_cycle")
            .get()
        )
        if doc.exists:
            data = doc.to_dict()
            data.pop("_firestore_transformer", None)
            return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("status read failed: %s", exc)
    return {"status": "no runs yet"}
