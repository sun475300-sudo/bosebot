"""Track RR — pre-encode hot FAQs at boot to cut first-query latency."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _load_faqs(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict) and "faqs" in data:
        data = data["faqs"]
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def _load_usage(path: str) -> Dict[str, int]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): int(v) for k, v in data.items() if isinstance(v, (int, float))} if isinstance(data, dict) else {}


def pick_hot_faqs(faqs, usage=None, *, top_n=10, key="question", id_key="id"):
    if top_n <= 0 or not faqs:
        return []
    usage = usage or {}
    scored = []
    for idx, item in enumerate(faqs):
        q = (item.get(key) or "").strip()
        if not q:
            continue
        rid = str(item.get(id_key, idx))
        score = float(usage.get(rid, 0)) - idx * 1e-6
        scored.append((score, q))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [q for _, q in scored[:top_n]]


def warmup(encode_fn: Callable[[str], Any], *, faq_path=None, usage_path=None, top_n=None, enabled=None) -> Dict[str, Any]:
    enabled = enabled if enabled is not None else os.environ.get("EMBEDDING_WARMUP_ENABLED", "1").lower() in ("1","true","yes")
    if not enabled:
        return {"ran": False, "reason": "disabled", "encoded": 0}
    n = top_n if top_n is not None else int(os.environ.get("EMBEDDING_WARMUP_TOP_N", "10"))
    faq_path = faq_path or os.environ.get("EMBEDDING_WARMUP_FAQ_PATH", os.path.join("data","faq.json"))
    usage_path = usage_path or os.environ.get("EMBEDDING_WARMUP_USAGE_PATH", "")
    faqs = _load_faqs(faq_path)
    if not faqs:
        return {"ran": False, "reason": "no_faqs", "encoded": 0, "faq_path": faq_path}
    usage = _load_usage(usage_path) if usage_path else {}
    questions = pick_hot_faqs(faqs, usage, top_n=n)
    start = time.time()
    encoded = errors = 0
    for q in questions:
        try:
            encode_fn(q)
            encoded += 1
        except Exception:
            errors += 1
            logger.exception("warmup encode failed")
    return {"ran": True, "encoded": encoded, "errors": errors, "top_n": n, "elapsed_ms": int((time.time()-start)*1000), "faq_path": faq_path}
