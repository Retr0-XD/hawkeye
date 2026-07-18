"""Unit tests for the ML Service (pure logic, no GCP creds needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings, get_settings
from app.features import feature_columns
from app.models import predict_anomaly, predict_failure


def test_settings_defaults():
    s = Settings()
    assert s.gcp_project_id == "dice-master-the-platform"
    assert s.anomaly_threshold == 0.7
    assert s.failure_threshold == 0.7


def test_feature_columns_stable():
    cols = feature_columns()
    assert "cpu_percent" in cols
    assert "cost_daily" in cols
    assert len(cols) == 8


def test_predict_anomaly_no_model_returns_safe():
    # No trained model + empty features -> not an anomaly, score 0.
    score, is_anom = predict_anomaly({})
    assert score == 0.0
    assert is_anom is False


def test_predict_failure_no_model_returns_safe():
    prob, is_risk = predict_failure({})
    assert prob == 0.0
    assert is_risk is False


def test_predict_anomaly_extreme_vector_flags():
    # Build a fake Isolation Forest-like model via monkeypatch is overkill;
    # instead verify the function signature + threshold logic with a stub model.
    class _Stub:
        def score_samples(self, X):
            # Return very negative => highly anomalous.
            return [-0.9]

    # Non-zero feature vector (idle/zero vectors are treated as neutral).
    feats = {c: 50.0 for c in feature_columns()}
    score, is_anom = predict_anomaly(feats, model=_Stub())
    assert is_anom is True
    assert 0.0 <= score <= 1.0


def test_predict_anomaly_zero_vector_neutral():
    # All-zero (idle serverless) features must NOT be flagged as anomalies.
    score, is_anom = predict_anomaly({c: 0.0 for c in feature_columns()})
    assert is_anom is False
    assert score == 0.0
