"""Tests for Track TT — single-query quality evaluation endpoint."""

from __future__ import annotations

import json

import pytest
from flask import Flask

from src.quality_evaluate import (
    FEATURE_NAMES,
    evaluate,
    register_evaluate_routes,
)


def test_evaluate_returns_seven_features_and_prediction():
    out = evaluate("비용", "5만원입니다 https://x 자세히 안내 드립니다")
    assert out["feature_names"] == list(FEATURE_NAMES)
    assert len(out["features"]) == 7
    assert 0.0 <= out["prediction"] <= 1.0
    assert len(out["contributions"]) == 7
    assert len(out["top_contributors"]) <= 3


def test_evaluate_uses_loaded_model_when_present(tmp_path):
    p = tmp_path / "model.json"
    coeffs = [0.0, 0.5, 0.5, 0.0, 0.0, 0.5, 0.0]
    p.write_text(json.dumps({"coefficients": coeffs}), encoding="utf-8")
    out = evaluate("비용", "5만원 https://x", model_path=str(p))
    assert out["model_loaded"] is True
    assert out["prediction"] > 0.0
    # Each contribution is value * coefficient
    for c, raw_c in zip(out["contributions"], coeffs):
        assert c["contribution"] == pytest.approx(c["value"] * raw_c)


def test_evaluate_endpoint_400_when_answer_missing():
    app = Flask(__name__)
    register_evaluate_routes(app)
    client = app.test_client()
    resp = client.post("/api/admin/quality/evaluate", json={"query": "x"})
    assert resp.status_code == 400


def test_evaluate_endpoint_returns_json():
    app = Flask(__name__)
    register_evaluate_routes(app)
    client = app.test_client()
    resp = client.post(
        "/api/admin/quality/evaluate",
        json={"query": "비용", "answer": "5만원 https://x 안내 드립니다"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["model_loaded"] in (True, False)  # depends on whether model file exists
    assert "features" in body and len(body["features"]) == 7
    assert 0.0 <= body["prediction"] <= 1.0


def test_auth_decorator_is_applied():
    """Ensure the caller's auth_required wraps the route."""
    app = Flask(__name__)
    calls = []

    def fake_auth(fn):
        def wrapped(*a, **k):
            calls.append("auth_check")
            return fn(*a, **k)
        wrapped.__name__ = fn.__name__
        return wrapped

    register_evaluate_routes(app, auth_required=fake_auth)
    client = app.test_client()
    client.post("/api/admin/quality/evaluate", json={"answer": "ok"})
    assert calls == ["auth_check"]
