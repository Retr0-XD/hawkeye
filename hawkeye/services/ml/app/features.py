"""Feature extraction for ML models.

Pulls historical metrics + costs from BigQuery (the `hawkeye` dataset) and
shapes them into feature matrices for training and inference.

Feature vector per resource (from architecture doc):
  cpu_percent, memory_percent, network_egress, error_rate,
  age_days, cost_daily, cost_trend, utilization_variance
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd

from .config import Settings, get_settings
from .gcp_clients import get_bigquery_client

logger = logging.getLogger("hawkeye.ml.features")

# In-memory cache of the built feature matrix. Rebuilt on retrain or TTL expiry.
# Avoids re-querying BigQuery on every single prediction (keeps p95 < 100ms).
_feature_cache: dict = {"ts": None, "fm": None}


def get_feature_matrix(ttl_seconds: int = 300) -> pd.DataFrame:
    """Return the cached feature matrix, rebuilding if stale/missing."""
    from datetime import datetime as _dt

    now = _dt.now(timezone.utc)
    ts = _feature_cache.get("ts")
    fm = _feature_cache.get("fm")
    if fm is not None and ts is not None:
        if (now - ts).total_seconds() < ttl_seconds:
            return fm
    fm = build_feature_matrix(load_metrics_df(), load_costs_df())
    _feature_cache["ts"] = now
    _feature_cache["fm"] = fm
    return fm


def invalidate_feature_cache() -> None:
    _feature_cache["ts"] = None
    _feature_cache["fm"] = None


def _metrics_query(settings: Settings, days: int) -> str:
    return f"""
    SELECT
        resource_id,
        timestamp,
        AVG(cpu_percent) AS cpu_percent,
        AVG(memory_percent) AS memory_percent,
        AVG(network_out_bytes) AS network_out_bytes,
        AVG(error_rate_percent) AS error_rate_percent
    FROM `{settings.gcp_project_id}.{settings.bq_dataset}.metrics`
    WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    GROUP BY resource_id, timestamp
    """


def _costs_query(settings: Settings, days: int) -> str:
    return f"""
    SELECT
        resource_id,
        date,
        SUM(daily_cost) AS daily_cost
    FROM `{settings.gcp_project_id}.{settings.bq_dataset}.billing`
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
    GROUP BY resource_id, date
    """


def load_metrics_df(days: Optional[int] = None) -> pd.DataFrame:
    """Return a DataFrame of per-timestamp metrics grouped by resource."""
    settings = get_settings()
    days = days or settings.training_history_days
    try:
        client = get_bigquery_client()
        df = client.query(_metrics_query(settings, days)).to_dataframe()
        if df.empty:
            return df
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as exc:  # noqa: BLE001
        logger.warning("metrics load failed: %s", exc)
        return pd.DataFrame()


def load_costs_df(days: Optional[int] = None) -> pd.DataFrame:
    """Return a DataFrame of per-day costs grouped by resource."""
    settings = get_settings()
    days = days or settings.training_history_days
    try:
        client = get_bigquery_client()
        df = client.query(_costs_query(settings, days)).to_dataframe()
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df
    except Exception as exc:  # noqa: BLE001
        logger.warning("costs load failed: %s", exc)
        return pd.DataFrame()


def build_feature_matrix(metrics_df: pd.DataFrame, costs_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw metrics/costs into one feature row per resource.

    Returns columns:
      resource_id, cpu_percent, memory_percent, network_out_bytes,
      error_rate_percent, age_days, cost_daily, cost_trend, utilization_var
    """
    if metrics_df.empty:
        return pd.DataFrame()

    # Per-resource aggregates from metrics.
    agg = (
        metrics_df.groupby("resource_id")
        .agg(
            cpu_percent=("cpu_percent", "mean"),
            memory_percent=("memory_percent", "mean"),
            network_out_bytes=("network_out_bytes", "mean"),
            error_rate_percent=("error_rate_percent", "mean"),
            utilization_var=("cpu_percent", "var"),
        )
        .reset_index()
    )
    agg["utilization_var"] = agg["utilization_var"].fillna(0.0)

    # Cost features (daily average + simple trend slope).
    if not costs_df.empty:
        cost_agg = (
            costs_df.groupby("resource_id")
            .agg(cost_daily=("daily_cost", "mean"))
            .reset_index()
        )
        # Trend: compare first half vs second half average.
        costs_df = costs_df.sort_values("date")
        trends = []
        for rid, g in costs_df.groupby("resource_id"):
            g = g.reset_index(drop=True)
            half = max(1, len(g) // 2)
            early = g["daily_cost"].iloc[:half].mean()
            late = g["daily_cost"].iloc[half:].mean()
            trend = 0.0 if early == 0 else (late - early) / early
            trends.append({"resource_id": rid, "cost_trend": trend})
        trend_df = pd.DataFrame(trends)
        agg = agg.merge(cost_agg, on="resource_id", how="left").merge(
            trend_df, on="resource_id", how="left"
        )
    else:
        agg["cost_daily"] = 0.0
        agg["cost_trend"] = 0.0

    # Age in days (from earliest metric timestamp to now).
    now = datetime.now(timezone.utc)
    first_seen = metrics_df.groupby("resource_id")["timestamp"].min()
    agg["age_days"] = agg["resource_id"].map(
        lambda r: (now - first_seen.get(r, now)).days
    )

    fill = {
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "network_out_bytes": 0.0,
        "error_rate_percent": 0.0,
        "utilization_var": 0.0,
        "cost_daily": 0.0,
        "cost_trend": 0.0,
    }
    agg = agg.fillna(fill)
    return agg


def feature_columns() -> List[str]:
    return [
        "cpu_percent",
        "memory_percent",
        "network_out_bytes",
        "error_rate_percent",
        "age_days",
        "cost_daily",
        "cost_trend",
        "utilization_var",
    ]


def extract_features_for_resource(
    resource_id: str, metrics_df: pd.DataFrame = None, costs_df: pd.DataFrame = None
) -> Dict[str, float]:
    """Single-resource feature dict (for online inference)."""
    fm = get_feature_matrix()
    if fm.empty:
        return {}
    row = fm[fm["resource_id"] == resource_id]
    if row.empty:
        return {}
    row = row.iloc[0]
    return {c: float(row.get(c, 0.0)) for c in feature_columns()}
