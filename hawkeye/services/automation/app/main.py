"""FastAPI entry point for the Hawkeye Automation Service (Week 8).

Endpoints:
  GET  /livez            liveness
  GET  /                info
  POST /automation/run  process all approved recommendations now
  GET  /automation/log  recent automation log entries
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from .config import get_settings
from .gcp_clients import get_firestore_client
from .orchestrator import run_automation

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("hawkeye.automation.main")

app = FastAPI(title="Hawkeye Automation Service", version="0.1.0")


@app.get("/livez")
async def livez():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "hawkeye-automation", "status": "running", "dry_run": get_settings().dry_run}


@app.post("/automation/run")
async def automation_run():
    return JSONResponse(content=run_automation())


@app.get("/automation/log")
async def automation_log(limit: int = Query(50, ge=1, le=200)):
    settings = get_settings()
    docs = (
        get_firestore_client()
        .collection(settings.fs_automation_log)
        .order_by("at", direction="DESCENDING")
        .limit(limit)
        .stream()
    )
    return JSONResponse(content={"items": [d.to_dict() for d in docs]})
