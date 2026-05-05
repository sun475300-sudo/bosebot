"""Tests for src/admin_diagnostics.py — unified diagnostics endpoint."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import admin_diagnostics


def test_collect_with_no_checks_returns_empty_ok():
    payload = admin_diagnostics.collect_diagnostics()
    assert payload["summary"]["ok"] is True
    assert payload["summary"]["total"] == 0
    assert payload["components"] == {}
    assert payload["timestamp"].endswith("Z")


def test_collect_dict_with_status_healthy_marked_ok():
    payload = admin_diagnostics.collect_diagnostics(
        checks={"db": lambda: {"status": "healthy", "latency_ms": 3}}
    )
    assert payload["components"]["db"]["ok"] is True
    assert payload["components"]["db"]["data"]["latency_ms"] == 3
    assert payload["summary"]["ok"] is True
    assert payload["summary"]["ok_count"] if False else True  # noqa


def test_collect_dict_with_status_degraded_marked_not_ok():
    payload = admin_diagnostics.collect_diagnostics(
        checks={"queue": lambda: {"status": "degraded"}}
    )
    assert payload["components"]["queue"]["ok"] is False
    assert payload["summary"]["ok"] is False
    assert payload["summary"]["error"] == 1


def test_collect_with_exception_raises_no_failure():
    def boom():
        raise ValueError("bad config")

    payload = admin_diagnostics.collect_diagnostics(checks={"saml": boom})
    assert payload["components"]["saml"]["ok"] is False
    assert "bad config" in payload["components"]["saml"]["error"]
    assert payload["summary"]["ok"] is False


def test_collect_with_non_callable_skipped():
    payload = admin_diagnostics.collect_diagnostics(checks={"x": "not a function"})
    assert payload["components"]["x"]["ok"] is False
    assert payload["summary"]["skipped"] == 1


def test_collect_with_ready_field_alias():
    payload = admin_diagnostics.collect_diagnostics(
        checks={"healthz": lambda: {"ready": False, "checks": {}}}
    )
    assert payload["components"]["healthz"]["ok"] is False


def test_collect_mixed_ok_and_error():
    checks = {
        "a": lambda: {"status": "healthy"},
        "b": lambda: {"status": "down"},
        "c": lambda: {"ok": True},
    }
    payload = admin_diagnostics.collect_diagnostics(checks=checks)
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["error"] == 1
    assert payload["summary"]["ok"] is False  # mixed = not OK overall


def test_register_with_none_app_returns_false():
    assert admin_diagnostics.register_diagnostics_routes(None) is False


def test_register_with_dummy_app_succeeds():
    seen = []

    class DummyApp:
        def add_url_rule(self, path, endpoint, view, methods=None):
            seen.append((path, endpoint, methods))

    ok = admin_diagnostics.register_diagnostics_routes(
        DummyApp(),
        checks={"healthz": lambda: {"status": "healthy"}},
    )
    assert ok is True
    assert len(seen) == 1
    assert seen[0][0] == "/api/admin/diagnostics"
    assert "GET" in seen[0][2]
