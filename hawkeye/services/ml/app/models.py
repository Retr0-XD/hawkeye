"""ML models for Hawkeye: anomaly detection, failure prediction, cost forecast.

Each model is trained on BigQuery historical data and persisted to a local
joblib file (Cloud Run ephemeral disk is fine for MVP; models are small).
Inference is stateless and cached by the serving layer.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from .config import Settings, get_settings
from .features import (
    build_feature_matrix,
    extract_features_for_resource,
    feature_columns,
    load_costs_df,
    load_metrics_df,
)

logger = logging.getLogger("hawkeye.ml.models")

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
ANOMALY_PATH = os.path.join(MODEL_DIR, "anomaly.joblib")
FAILURE_PATH = os.path.join(MODEL_DIR, "failure.joblib")


# --------------------------------------------------------------------------
# Anomaly detection (Isolation Forest, unsupervised)
# --------------------------------------------------------------------------
def train_anomaly_detector() -> Optional[object]:
    """Train an Isolation Forest on resource feature vectors.

    Only trains when there is *real* telemetry (cpu/memory/network/error/cost).
    If every resource reports zero usage (e.g. billing + monitoring not yet
    wired up), training would learn "all zeros = normal" and then flag the
    tiniest non-zero field (like age_days) as an anomaly for *every* resource —
    pure noise. In that case we skip training and the model stays untrained,
    so predictions return a neutral, non-anomalous score.
    """
    settings = get_settings()
    fm = build_feature_matrix(load_metrics_df(), load_costs_df())
    if fm.empty or len(fm) < settings.min_training_samples:
        logger.warning(
            "Not enough samples to train anomaly detector (%d < %d)",
            len(fm),
            settings.min_training_samples,
        )
        return None
    # Real-signal columns (exclude age_days, which is always present metadata).
    signal_cols = [
        "cpu_percent", "memory_percent", "network_out_bytes",
        "error_rate_percent", "cost_daily", "cost_trend", "utilization_var",
    ]
    if fm[signal_cols].abs().sum().sum() < 1e-6:
        logger.warning(
            "No real telemetry available (all-zero usage) — skipping anomaly "
            "model training to avoid degenerate 'everything is anomalous' output."
        )
        return None
    X = fm[feature_columns()].fillna(0.0).to_numpy()
    from sklearn.ensemble import IsolationForest

    model = IsolationForest(
        contamination="auto", random_state=42, n_estimators=100
    )
    model.fit(X)
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, ANOMALY_PATH)
    logger.info("Trained anomaly detector on %d resources", len(fm))
    return model


def load_anomaly_detector() -> Optional[object]:
    if os.path.exists(ANOMALY_PATH):
        return joblib.load(ANOMALY_PATH)
    return None


def predict_anomaly(features: Dict[str, float], model=None) -> Tuple[float, bool]:
    """Return (anomaly_score 0-1, is_anomaly). Higher score = more anomalous.

    Isolation Forest ``score_samples`` returns higher values for *normal*
    points (roughly 0..1, occasionally slightly negative for outliers).
    We map it to an anomaly score via a sigmoid centred at 0.5 so that the
    score is well-distributed instead of saturating at 1.0 for every point.
    """
    settings = get_settings()
    model = model or load_anomaly_detector()
    if model is None or not features:
        return 0.0, False
    X = np.array([[features.get(c, 0.0) for c in feature_columns()]])
    # A resource with *no* real telemetry (cpu/memory/network/error/cost all
    # zero) is not anomalous — it is simply unobserved (idle serverless, or
    # billing/monitoring not yet wired up). age_days is always-present metadata
    # and must NOT count as "signal". Flagging every unobserved resource as an
    # anomaly is noise, not signal, so we return a neutral, non-anomalous score.
    signal_cols = [
        "cpu_percent", "memory_percent", "network_out_bytes",
        "error_rate_percent", "cost_daily", "cost_trend", "utilization_var",
    ]
    if sum(abs(features.get(c, 0.0)) for c in signal_cols) < 1e-6:
        return 0.0, False
    raw = float(model.score_samples(X)[0])  # higher = more normal
    # Isolation Forest scores are roughly centred at 0 (normal points ~0..0.5,
    # outliers negative). Centre the sigmoid at 0 so that normal points get a
    # low anomaly score and genuine outliers (raw < 0) get a high score.
    score = float(1.0 / (1.0 + np.exp(4.0 * raw)))
    return round(score, 4), score >= settings.anomaly_threshold


# --------------------------------------------------------------------------
# Failure prediction (Gradient Boosting, supervised)
# --------------------------------------------------------------------------
def train_failure_predictor() -> Optional[object]:
    """Train a gradient-boosting classifier.

    Label heuristic: a resource is a "failure risk" if its error_rate is high
    AND utilization variance is high (unstable) AND it is old. This is a
    self-supervised proxy since we have no historical incident labels yet.
    """
    settings = get_settings()
    fm = build_feature_matrix(load_metrics_df(), load_costs_df())
    if fm.empty or len(fm) < settings.min_training_samples:
        logger.warning("Not enough samples to train failure predictor")
        return None

    # Synthetic label: unstable + error-prone + aged.
    err = fm["error_rate_percent"].fillna(0.0)
    var = fm["utilization_var"].fillna(0.0)
    age = fm["age_days"].fillna(0.0)
    label = (
        (err > err.quantile(0.75))
        & (var > var.quantile(0.75))
        & (age > age.quantile(0.5))
    ).astype(int)
    if label.sum() == 0 or label.sum() == len(label):
        logger.warning("Failure labels degenerate; skipping training")
        return None

    X = fm[feature_columns()].fillna(0.0).to_numpy()
    from sklearn.ensemble import GradientBoostingClassifier

    model = GradientBoostingClassifier(random_state=42)
    model.fit(X, label.to_numpy())
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, FAILURE_PATH)
    logger.info("Trained failure predictor (positives=%d)", int(label.sum()))
    return model


def load_failure_predictor() -> Optional[object]:
    if os.path.exists(FAILURE_PATH):
        return joblib.load(FAILURE_PATH)
    return None


def predict_failure(features: Dict[str, float], model=None) -> Tuple[float, bool]:
    """Return (failure_probability 0-1, is_high_risk)."""
    settings = get_settings()
    model = model or load_failure_predictor()
    if model is None or not features:
        return 0.0, False
    X = np.array([[features.get(c, 0.0) for c in feature_columns()]])
    proba = model.predict_proba(X)[0]
    p = float(proba[1]) if proba.shape[0] > 1 else 0.0
    return p, p >= settings.failure_threshold


# --------------------------------------------------------------------------
# Cost forecasting (ARIMA, time-series)
# --------------------------------------------------------------------------
def forecast_cost(resource_id: str, days: int = 7) -> Optional[Dict[str, float]]:
    """Forecast next `days` of daily cost via ARIMA on historical billing.

    Returns dict with usual_daily, predicted_daily, predicted_total,
    spike (bool). Returns None if insufficient history.
    """
    settings = get_settings()
    costs = load_costs_df(days=max(30, settings.training_history_days))
    if costs.empty:
        return None
    series = (
        costs[costs["resource_id"] == resource_id]
        .sort_values("date")["daily_cost"]
        .reset_index(drop=True)
    )
    if len(series) < 7:
        return None

    try:
        from statsmodels.tsa.arima.model import ARIMA

        model = ARIMA(series, order=(1, 1, 1)).fit()
        forecast = model.forecast(steps=days)
        forecast = [max(0.0, float(v)) for v in forecast]
    except Exception as exc:  # noqa: BLE001
        logger.warning("ARIMA forecast failed for %s: %s", resource_id, exc)
        return None

    usual = float(series.mean())
    predicted_total = float(sum(forecast))
    spike = (predicted_total / days) > (usual * settings.cost_spike_ratio) if usual > 0 else False
    return {
        "usual_daily": round(usual, 4),
        "predicted_daily": round(predicted_total / days, 4),
        "predicted_total": round(predicted_total, 4),
        "spike": bool(spike),
    }


# --------------------------------------------------------------------------
# Convenience: run all predictions for one resource (online inference)
# --------------------------------------------------------------------------
def predict_resource(resource_id: str) -> Dict:
    """Full prediction bundle for a single resource."""
    features = extract_features_for_resource(resource_id)
    if not features:
        return {"resource_id": resource_id, "predictable": False}

    anomaly_model = load_anomaly_detector()
    failure_model = load_failure_predictor()
    anomaly_score, is_anomaly = predict_anomaly(features, anomaly_model)
    failure_prob, is_risk = predict_failure(features, failure_model)
    cost = forecast_cost(resource_id)

    return {
        "resource_id": resource_id,
        "predictable": True,
        "features": features,
        "anomaly": {"score": round(anomaly_score, 4), "is_anomaly": is_anomaly},
        "failure": {"probability": round(failure_prob, 4), "is_high_risk": is_risk},
        "cost_forecast": cost,
    }
