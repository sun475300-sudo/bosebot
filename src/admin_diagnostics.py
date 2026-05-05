"""관리자용 통합 진단 엔드포인트.

여러 상태 엔드포인트(``/healthz``, ``/api/ws/status``,
``/api/auth/saml/status``, ``/api/chat/stream/stats``)를 하나로 묶어
한 번의 호출로 시스템 전체 상태를 확인할 수 있게 한다.

각 sub-check 는 콜러블(zero-arg → dict)로 주입되며,
누락되거나 예외를 일으켜도 graceful degrade 한다.

Usage::

    from src.admin_diagnostics import register_diagnostics_routes

    register_diagnostics_routes(
        app,
        checks={
            "healthz":     lambda: healthz_routes.readiness_payload(hm),
            "ws":          ws_status_provider,
            "saml":        saml_status_provider,
            "stream":      stream_stats_provider,
        },
    )
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def collect_diagnostics(
    checks: Optional[Dict[str, Callable[[], Any]]] = None,
) -> Dict[str, Any]:
    """주입된 체크 함수들을 모두 호출해 결과를 합친다.

    각 체크의 결과는 dict로 가정하지만, 그 외 타입(예: bool, str)도
    그대로 ``value`` 키에 보관한다. 예외를 던지면 ``ok=False``,
    ``error`` 메시지를 기록한다.

    Returns:
        ``{"summary": {...}, "components": {...}, "timestamp": ...}``
    """
    components: Dict[str, Any] = {}
    counts = {"ok_count": 0, "error": 0, "skipped": 0}
    started = time.time()

    if checks:
        for name, fn in checks.items():
            if not callable(fn):
                components[name] = {"ok": False, "error": "not callable"}
                counts["skipped"] += 1
                continue
            t0 = time.time()
            try:
                result = fn()
                elapsed_ms = round((time.time() - t0) * 1000.0, 2)
                if isinstance(result, dict):
                    components[name] = {
                        "ok": _result_is_ok(result),
                        "elapsed_ms": elapsed_ms,
                        "data": result,
                    }
                else:
                    components[name] = {
                        "ok": True,
                        "elapsed_ms": elapsed_ms,
                        "value": result,
                    }
                if components[name]["ok"]:
                    counts["ok_count"] += 1
                else:
                    counts["error"] += 1
            except Exception as exc:
                components[name] = {
                    "ok": False,
                    "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
                    "error": str(exc),
                }
                counts["error"] += 1

    overall_ok = counts["error"] == 0
    return {
        "summary": {
            "ok": overall_ok,
            "total": len(components),
            **counts,
            "elapsed_ms": round((time.time() - started) * 1000.0, 2),
        },
        "components": components,
        "timestamp": _now_iso(),
    }


def _result_is_ok(result: Dict[str, Any]) -> bool:
    """체크 결과 dict로부터 ok 여부를 추출."""
    if "ok" in result:
        return bool(result["ok"])
    if "ready" in result:
        return bool(result["ready"])
    status = str(result.get("status", "")).lower()
    if status in ("healthy", "ok", "ready", "alive", "up"):
        return True
    if status in ("degraded", "unhealthy", "down", "not_ready", "error"):
        return False
    # Unknown / not specified → optimistic
    return True


def register_diagnostics_routes(
    app: Any,
    checks: Optional[Dict[str, Callable[[], Any]]] = None,
    path: str = "/api/admin/diagnostics",
) -> bool:
    """``GET {path}`` 라우트를 등록.

    Returns:
        등록 성공 시 True, app 호환 안 되면 False.
    """
    if app is None or not hasattr(app, "add_url_rule"):
        return False

    def _view():  # pragma: no cover - thin wrapper
        payload = collect_diagnostics(checks)
        code = 200 if payload["summary"]["ok"] else 503
        try:
            from flask import jsonify
            return jsonify(payload), code
        except Exception:
            return json.dumps(payload), code

    try:
        app.add_url_rule(path, "admin_diagnostics", _view, methods=["GET"])
        return True
    except Exception:
        return False


__all__ = [
    "collect_diagnostics",
    "register_diagnostics_routes",
]
