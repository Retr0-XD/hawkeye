"""FastAPI entrypoint for Hawkeye Budget Guard.

Endpoints:
  GET  /livez            -> liveness
  GET  /               -> info
  POST /guard/run         -> run the free-zone check now
  GET  /guard/status       -> current cost + suspension state
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import get_settings
from .orchestrator import run_guard

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("hawkeye.budget-guard")

app = FastAPI(title="Hawkeye Budget Guard", version="0.1.0")


@app.get("/livez")
async def livez():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "hawkeye-budget-guard", "status": "running"}


@app.post("/guard/run")
async def guard_run():
    return JSONResponse(content=run_guard())


@app.get("/guard/status")
async def guard_status():
    from .billing import get_month_to_date_cost
    from .config import get_settings
    from .guard import get_state

    settings = get_settings()
    cost = get_month_to_date_cost(settings)
    state = get_state(settings)
    return JSONResponse(
        content={
            "cost_mtd_usd": round(cost, 4),
            "cap_usd": settings.monthly_cost_cap_usd,
            "suspended": state.get("suspended", False),
            "suspended_month": state.get("suspended_month"),
            "last_cost_usd": state.get("last_cost_usd"),
        }
    )
