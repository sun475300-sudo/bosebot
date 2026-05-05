"""Tests for src/healthz_routes.py — live/ready probe split."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import healthz_routes


def test_liveness_payload_has_required_fields():
    payload = healthz_routes.liveness_payload()
    assert payload["status"] == "alive"
    assert "pid" in payload and isinstance(payload["pid"], int)
    assert "uptime_sec" in payload and payload["uptime_sec"] >= 0
    assert "timestamp" in payload and payload["timestamp"].endswith("Z")


def test_readiness_with_no_monitor_is_ready():
    """No checks configured ⇒ ready by default."""
    payload = healthz_routes.readiness_payload()
    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert payload["checks"] == {}


def test_readiness_with_extra_check_failure():
    payload = healthz_routes.readiness_payload(
        extra_checks={"db": lambda: True, "queue": lambda: False}
    )
    assert payload["status"] == "not_ready"
    assert payload["ready"] is False
    assert payload["checks"]["db"]["ok"] is True
    assert payload["checks"]["queue"]["ok"] is False


def test_readiness_with_failing_extra_check_exception():
    def boom():
        raise RuntimeError("nope")

    payload = healthz_routes.readiness_payload(extra_checks={"x": boom})
    assert payload["ready"] is False
    assert payload["checks"]["x"]["ok"] is False
    assert "error" in payload["checks"]["x"]


def test_readiness_with_health_monitor_healthy():
    class FakeHM:
        def check_database(self):
            return {"status": "healthy"}

        def check_faq(self):
            return {"status": "healthy"}

    payload = healthz_routes.readiness_payload(health_monitor=FakeHM())
    assert payload["ready"] is True
    assert payload["checks"]["database"]["ok"] is True
    assert payload["checks"]["faq"]["ok"] is True


def test_readiness_with_health_monitor_degraded_marks_not_ready():
    class FakeHM:
        def check_database(self):
            return {"status": "degraded"}

    payload = healthz_routes.readiness_payload(health_monitor=FakeHM())
    assert payload["ready"] is False
    assert payload["checks"]["database"]["ok"] is False


def test_register_healthz_routes_with_none_app_returns_false():
    assert healthz_routes.register_healthz_routes(None) is False


def test_register_healthz_routes_with_dummy_app_succeeds():
    """Object that quacks like Flask app.add_url_rule should be accepted."""
    rules = []

    class DummyApp:
        def add_url_rule(self, path, endpoint, view, methods=None):
            rules.append((path, endpoint))

    ok = healthz_routes.register_healthz_routes(DummyApp())
    assert ok is True
    paths = {p for p, _ in rules}
    assert "/healthz/live" in paths
    assert "/healthz/ready" in paths
    assert "/healthz" in paths
