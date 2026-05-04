"""Track TT — single-query quality evaluation endpoint (depends Track NN).

Builds on top of Tracks EE (quality_model) + NN (quality_dashboard).
Adds a focused POST endpoint that lets admins paste a candidate
``query``/``answer`` pair and see:

  - the 7 raw feature values
  - the model's predicted helpfulness (0..1)
  - which features contributed most to the prediction

The endpoint is gated by an ``auth_required`` decorator the caller passes
in (so it composes with whatever admin-auth the app already uses).

Wire-up::

    from src.quality_evaluate import register_evaluate_routes
    register_evaluate_routes(app, auth_required=admin_only)
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

# Track EE may or may not be present on this branch — degrade gracefully.
try:
    from src.quality_model import (  # type: ignore
        FEATURE_NAMES,
        QualityModel,
        extract_features,
    )
    HAS_QUALITY_MODEL = True
except Exception:  # pragma: no cover
    HAS_QUALITY_MODEL = False
    FEATURE_NAMES = (
        "bias",
        "answer_len_norm",
        "answer_has_link",
        "answer_has_number",
        "query_len_norm",
        "answer_has_keyword_match",
        "answer_uses_polite_form",
    )

    def extract_features(answer: str, query: str = "") -> List[float]:
        a, q = answer or "", query or ""
        link = 1.0 if ("http://" in a or "https://" in a) else 0.0
        num = 1.0 if any(c.isdigit() for c in a) else 0.0
        kw = 0.0
        if q:
            toks = {t for t in q.split() if len(t) >= 2}
            if toks and any(t in a for t in toks):
                kw = 1.0
        polite = 1.0 if any(m in a for m in ("습니다", "니다", "드립니다", "입니다", "세요")) else 0.0
        return [1.0, min(len(a) / 500.0, 4.0), link, num, min(len(q) / 100.0, 4.0), kw, polite]

    class QualityModel:  # type: ignore
        def __init__(self, coefficients=None):
            self.coefficients = coefficients or [0.0] * len(FEATURE_NAMES)

        @classmethod
        def load_json(cls, path: str):
            import json
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return cls(coefficients=list(d.get("coefficients", [])))

        def predict(self, features):
            if not self.coefficients:
                return 0.5
            raw = sum(c * f for c, f in zip(self.coefficients, features))
            return max(0.0, min(1.0, raw))


DEFAULT_MODEL_PATH = os.path.join("config", "quality_model.json")


def evaluate(query: str, answer: str, *, model_path: str = DEFAULT_MODEL_PATH) -> Dict[str, Any]:
    """Return the evaluation payload for one (query, answer) pair."""
    feats = extract_features(answer, query)
    model: Optional[QualityModel] = None
    try:
        model = QualityModel.load_json(model_path)
    except FileNotFoundError:
        model = None
    except Exception:
        model = None

    coeffs = list(model.coefficients) if (model and model.coefficients) else [0.0] * len(FEATURE_NAMES)
    contributions = [
        {"feature": name, "value": v, "coefficient": c, "contribution": v * c}
        for name, v, c in zip(FEATURE_NAMES, feats, coeffs)
    ]
    if model is not None:
        prediction = model.predict(feats)
    else:
        prediction = 0.5
    # Pick top-3 contributors by absolute value (excluding bias).
    top = sorted(
        (c for c in contributions if c["feature"] != "bias"),
        key=lambda c: abs(c["contribution"]),
        reverse=True,
    )[:3]
    return {
        "model_loaded": model is not None,
        "model_path": model_path,
        "feature_names": list(FEATURE_NAMES),
        "features": feats,
        "prediction": prediction,
        "contributions": contributions,
        "top_contributors": top,
    }


def _noop_auth(fn):
    return fn


def register_evaluate_routes(
    app,
    *,
    auth_required: Callable = _noop_auth,
    model_path: str = DEFAULT_MODEL_PATH,
) -> None:
    """Mount POST /api/admin/quality/evaluate onto ``app``."""
    from flask import jsonify, request

    @app.route("/api/admin/quality/evaluate", methods=["POST"])
    @auth_required
    def quality_evaluate():
        body = request.get_json(silent=True) or {}
        query = (body.get("query") or "").strip()
        answer = (body.get("answer") or "").strip()
        if not answer:
            return jsonify({"error": "missing answer"}), 400
        return jsonify(evaluate(query, answer, model_path=model_path))
