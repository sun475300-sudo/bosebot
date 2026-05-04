"""Tests for src.law_auto_updater (background scheduler)."""

from __future__ import annotations

import os
import threading
import time
from typing import List

import pytest

from src import law_auto_updater as lau


# ------------------------------------------------------------------
# fakes
# ------------------------------------------------------------------

class _FakeAdmRulMgr:
    def __init__(self, changes_per_run: int = 1):
        self.calls = 0
        self.changes_per_run = changes_per_run
        self.update_calls = 0

    def sync_all(self, allow_html_fallback: bool = True) -> dict:
        self.calls += 1
        return {
            "checked_at": "now",
            "total_checked": 1,
            "changes_detected": self.changes_per_run,
            "errors": 0,
            "details": [{
                "admrul_seq": "2100000276240",
                "name": "TestNotice",
                "status": "changed" if self.changes_per_run else "unchanged",
            }],
        }

    def update_legal_references(self) -> dict:
        self.update_calls += 1
        return {"updated": 0, "total": 0}


class _FakeLawMgr:
    def __init__(self, changes_per_run: int = 0):
        self.calls = 0
        self.changes_per_run = changes_per_run

    def check_all(self) -> dict:
        self.calls += 1
        return {
            "total_checked": 0,
            "changes_detected": self.changes_per_run,
            "errors": 0,
        }

    def update_legal_references(self) -> dict:
        return {"updated": 0, "total": 0}


# ------------------------------------------------------------------
# fixtures
# ------------------------------------------------------------------

@pytest.fixture
def tmp_log(tmp_path):
    return str(tmp_path / "law_auto_update.log")


@pytest.fixture(autouse=True)
def _reset_singleton():
    lau.stop_auto_updater(timeout=1.0)
    yield
    lau.stop_auto_updater(timeout=1.0)


# ------------------------------------------------------------------
# tests
# ------------------------------------------------------------------

def test_disabled_via_env(tmp_log, monkeypatch):
    monkeypatch.setenv("LAW_AUTO_UPDATE_ENABLED", "false")
    upd = lau.LawAutoUpdater(log_path=tmp_log)
    assert upd.enabled is False
    assert upd.start() is False  # no thread when disabled
    assert upd.is_running() is False


def test_run_once_invokes_callback_on_change(tmp_log):
    events: List[dict] = []
    upd = lau.LawAutoUpdater(
        enabled=True,
        interval_hours=0.05,
        initial_delay=0.0,
        on_change=lambda r: events.append(r),
        admrul_manager=_FakeAdmRulMgr(changes_per_run=1),
        law_manager=_FakeLawMgr(changes_per_run=0),
        log_path=tmp_log,
    )
    res = upd.run_once()
    assert res["status"] == "ok"
    assert res["changes_detected"] == 1
    assert len(events) == 1
    assert upd.total_changes == 1
    assert upd.total_runs == 1


def test_run_once_no_callback_when_no_change(tmp_log):
    events: List[dict] = []
    upd = lau.LawAutoUpdater(
        enabled=True,
        on_change=lambda r: events.append(r),
        admrul_manager=_FakeAdmRulMgr(changes_per_run=0),
        law_manager=_FakeLawMgr(changes_per_run=0),
        log_path=tmp_log,
    )
    res = upd.run_once()
    assert res["status"] == "ok"
    assert res["changes_detected"] == 0
    assert events == []  # callback NOT fired when nothing changed


def test_concurrent_run_once_is_locked(tmp_log):
    """Two concurrent run_once calls — only one executes; the other returns skipped_locked."""
    barrier = threading.Event()
    release = threading.Event()
    call_count = {"n": 0}

    class _SlowAdmRul(_FakeAdmRulMgr):
        def sync_all(self, allow_html_fallback: bool = True):
            call_count["n"] += 1
            barrier.set()
            release.wait(timeout=2.0)
            return super().sync_all(allow_html_fallback)

    upd = lau.LawAutoUpdater(
        enabled=True,
        admrul_manager=_SlowAdmRul(changes_per_run=0),
        law_manager=_FakeLawMgr(),
        log_path=tmp_log,
    )

    results = {}
    def _t1():
        results["a"] = upd.run_once()
    t = threading.Thread(target=_t1)
    t.start()
    assert barrier.wait(timeout=2.0)
    # second concurrent call should be skipped
    second = upd.run_once()
    release.set()
    t.join(timeout=3.0)
    assert second["status"] == "skipped_locked"
    assert results["a"]["status"] == "ok"
    assert call_count["n"] == 1


def test_thread_lifecycle_start_stop(tmp_log):
    upd = lau.LawAutoUpdater(
        enabled=True,
        interval_hours=0.05,
        initial_delay=0.0,
        admrul_manager=_FakeAdmRulMgr(changes_per_run=0),
        law_manager=_FakeLawMgr(),
        log_path=tmp_log,
    )
    assert upd.start() is True
    # second start should be a no-op
    assert upd.start() is False
    # let the thread run at least one cycle
    deadline = time.time() + 3.0
    while upd.total_runs == 0 and time.time() < deadline:
        time.sleep(0.05)
    assert upd.total_runs >= 1
    upd.stop(timeout=2.0)
    assert upd.is_running() is False


def test_status_dict_contains_expected_keys(tmp_log):
    upd = lau.LawAutoUpdater(
        enabled=True,
        admrul_manager=_FakeAdmRulMgr(changes_per_run=1),
        law_manager=_FakeLawMgr(),
        log_path=tmp_log,
    )
    upd.run_once()
    s = upd.status()
    for key in ("enabled", "running", "interval_hours", "last_run_at",
                "last_status", "next_run_at", "total_runs", "total_changes",
                "log_path"):
        assert key in s
    assert s["last_status"] == "ok"
    assert s["next_run_at"] is not None  # computed once last_run_at set


def test_singleton_start_returns_none_when_disabled(tmp_log, monkeypatch):
    monkeypatch.setenv("LAW_AUTO_UPDATE_ENABLED", "false")
    res = lau.start_auto_updater(log_path=tmp_log)
    assert res is None
    assert lau.get_auto_updater() is None


def test_callback_exception_does_not_crash_updater(tmp_log):
    def boom(_r):
        raise RuntimeError("boom")
    upd = lau.LawAutoUpdater(
        enabled=True,
        on_change=boom,
        admrul_manager=_FakeAdmRulMgr(changes_per_run=1),
        law_manager=_FakeLawMgr(),
        log_path=tmp_log,
    )
    # should not raise
    res = upd.run_once()
    assert res["status"] == "ok"  # the sync itself succeeded
