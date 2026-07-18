"""FastAPI entrypoint for the Hawkeye Ingestion Service.

Exposes:
  - GET  /livez            -> liveness probe (Cloud Run reserves /healthz)
  - GET  /                -> service info
  - POST /ingest/run      -> trigger a synchronous ingestion cycle
  - GET  /ingest/status   -> last sync info from Firestore

NOTE: Ingestion is triggered externally by the ``ingestion-tick`` Cloud
Scheduler job (every 5 min) which POSTs to /ingest/run. A long-running
in-process scheduler is intentionally NOT used: Cloud Run scales to 0, so an
internal loop would be unreliable and could double-run with the scheduler.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import get_settings
from .orchestrator import ingest_all_projects

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("hawkeye.ingestion")


app = FastAPI(title="Hawkeye Ingestion Service", version="0.1.0")


@app.get("/livez")
async def livez():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "hawkeye-ingestion", "status": "running"}


@app.post("/ingest/run")
async def ingest_run():
    summary = await ingest_all_projects()
    return JSONResponse(content=summary)


@app.get("/ingest/status")
async def ingest_status():
    from .gcp_clients import get_firestore_client

    settings = get_settings()
    try:
        db = get_firestore_client()
        doc = (
            db.collection(settings.firestore_state_collection)
            .document(settings.firestore_state_doc)
            .get()
        )
        if doc.exists:
            data = doc.to_dict()
            # Firestore returns DatetimeWithNanoseconds; make JSON-safe.
            last_sync = data.get("last_sync")
            if last_sync is not None:
                data["last_sync"] = str(last_sync)
            return JSONResponse(content=data)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(content={"error": str(exc)}, status_code=500)
    return JSONResponse(content={"last_sync": None})
