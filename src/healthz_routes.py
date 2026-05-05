"""헬스 체크 엔드포인트 (live/ready 분리).

Kubernetes/Docker 표준에 맞춘 두 가지 프로브 엔드포인트:

- ``/healthz/live``: 프로세스가 살아 있는지만 확인.
  거의 항상 ``200 OK``를 반환한다 (deadlock 등 치명적 상태일 때만 실패).
- ``/healthz/ready``: 트래픽을 받을 준비가 되었는지 확인.
  DB 연결, FAQ 로드, 외부 의존성을 체크한다.
- ``/healthz``: 기존 호환을 위한 alias (= ``/ready``).

Usage::

    from src.healthz_routes import register_healthz_routes
    register_healthz_routes(app, health_monitor=hm)

외부 의존성(Flask 등)이 없는 경우에도 import 가능하도록 graceful degrade.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, Optional

# 프로세스 시작 시각
_PROCESS_START = time.time()


def _now_iso() -> str:
    """UTC ISO 8601 timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def liveness_payload() -> Dict[str, Any]:
    """live 프로브 응답 본문.

    프로세스 PID, uptime, 시각만 반환한다. 외부 의존성 검사 없음.
    """
    return {
        "status": "alive",
        "pid": os.getpid(),
        "uptime_sec": round(time.time() - _PROCESS_START, 3),
        "timestamp": _now_iso(),
    }


def readiness_payload(
    health_monitor: Optional[Any] = None,
    extra_checks: Optional[Dict[str, Callable[[], bool]]] = None,
) -> Dict[str, Any]:
    """ready 프로브 응답 본문.

    Args:
        health_monitor: HealthMonitor 인스턴스 (선택).
            ``check_database`` / ``check_faq`` 메소드가 있으면 호출.
        extra_checks: 이름→bool 함수 dict. 각 함수의 반환값으로 ready 판정.

    Returns:
        ``{"status": "ready"|"not_ready", "checks": {...}, ...}``
    """
    checks: Dict[str, Dict[str, Any]] = {}
    overall_ready = True

    if health_monitor is not None:
        for method_name, check_key in (
            ("check_database", "database"),
            ("check_faq", "faq"),
        ):
            method = getattr(health_monitor, method_name, None)
            if not callable(method):
                continue
            try:
                result = method()
                status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
                ok = status == "healthy"
                checks[check_key] = {"ok": ok, "status": status}
                if not ok:
                    overall_ready = False
            except Exception as exc:  # pragma: no cover - defensive
                checks[check_key] = {"ok": False, "status": "error", "error": str(exc)}
                overall_ready = False

    if extra_checks:
        for name, fn in extra_checks.items():
            try:
                ok = bool(fn())
                checks[name] = {"ok": ok}
                if not ok:
                    overall_ready = False
            except Exception as exc:  # pragma: no cover - defensive
                checks[name] = {"ok": False, "error": str(exc)}
                overall_ready = False

    return {
        "status": "ready" if overall_ready else "not_ready",
        "ready": overall_ready,
        "checks": checks,
        "uptime_sec": round(time.time() - _PROCESS_START, 3),
        "timestamp": _now_iso(),
    }


def register_healthz_routes(
    app: Any,
    health_monitor: Optional[Any] = None,
    extra_checks: Optional[Dict[str, Callable[[], bool]]] = None,
) -> bool:
    """Flask 앱에 ``/healthz/live`` 및 ``/healthz/ready`` 라우트를 등록한다.

    Args:
        app: Flask 인스턴스 (또는 ``add_url_rule`` 메소드를 갖춘 객체).
        health_monitor: HealthMonitor 인스턴스 (선택).
        extra_checks: 추가 ready 체크 함수 dict (선택).

    Returns:
        등록 성공 시 True. ``app``이 None이거나 호환되지 않으면 False
        (graceful degrade).
    """
    if app is None or not hasattr(app, "add_url_rule"):
        return False

    def _live_view():  # pragma: no cover - thin wrapper
        try:
            from flask import jsonify
            return jsonify(liveness_payload()), 200
        except Exception:
            return json.dumps(liveness_payload()), 200

    def _ready_view():  # pragma: no cover - thin wrapper
        payload = readiness_payload(health_monitor, extra_checks)
        code = 200 if payload["ready"] else 503
        try:
            from flask import jsonify
            return jsonify(payload), code
        except Exception:
            return json.dumps(payload), code

    try:
        app.add_url_rule("/healthz/live", "healthz_live", _live_view, methods=["GET"])
        app.add_url_rule("/healthz/ready", "healthz_ready", _ready_view, methods=["GET"])
        # 기존 단일 /healthz는 ready alias로 동작
        app.add_url_rule(
            "/healthz", "healthz_alias", _ready_view, methods=["GET"]
        )
        return True
    except Exception:
        return False


__all__ = [
    "liveness_payload",
    "readiness_payload",
    "register_healthz_routes",
]
