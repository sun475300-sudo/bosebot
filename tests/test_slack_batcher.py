"""Tests for src.slack_batcher (track WW)."""

from __future__ import annotations

import pytest

from src.slack_batcher import MockSlackNotifier, SlackBatcher


class FakeClock:
    def __init__(self, t0: float = 1000.0):
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_dedup_collapses_identical_messages_with_count_suffix():
    n = MockSlackNotifier()
    clk = FakeClock()
    b = SlackBatcher(n, window_seconds=5.0, time_fn=clk)

    for _ in range(4):
        b.submit("#alerts", "law_api 503")

    assert b.buffered == 1  # all 4 collapsed
    res = b.flush()
    assert res.posted == 1
    assert res.suppressed == 3
    assert n.posts == [("#alerts", "law_api 503  (x4)")]


def test_distinct_messages_join_one_post_per_channel():
    n = MockSlackNotifier()
    b = SlackBatcher(n, window_seconds=10.0, time_fn=FakeClock())

    b.submit("#alerts", "A failed")
    b.submit("#alerts", "B failed")
    b.submit("#ops", "C failed")

    res = b.flush()
    assert res.posted == 2
    assert res.suppressed == 0
    posts = dict(n.posts)
    assert posts["#alerts"] == "A failed\nB failed"
    assert posts["#ops"] == "C failed"


def test_window_elapse_triggers_auto_flush():
    n = MockSlackNotifier()
    clk = FakeClock()
    b = SlackBatcher(n, window_seconds=5.0, time_fn=clk)

    b.submit("#alerts", "first")
    clk.advance(6.0)  # window passed
    b.submit("#alerts", "second")  # should flush "first" first

    # First message already delivered.
    assert ("#alerts", "first") in n.posts
    # "second" still buffered until next flush
    assert b.buffered == 1
    b.flush()
    assert ("#alerts", "second") in n.posts


def test_max_buffer_forces_flush():
    n = MockSlackNotifier()
    b = SlackBatcher(n, window_seconds=999.0, max_buffer=3, time_fn=FakeClock())

    b.submit("#alerts", "m1")
    b.submit("#alerts", "m2")
    assert n.posts == []  # not flushed yet
    b.submit("#alerts", "m3")  # 3rd distinct -> reaches max_buffer
    # auto-flushed
    assert len(n.posts) == 1
    assert "m1" in n.posts[0][1]
    assert "m3" in n.posts[0][1]
    assert b.buffered == 0


def test_empty_or_invalid_inputs_are_dropped_silently():
    n = MockSlackNotifier()
    b = SlackBatcher(n, time_fn=FakeClock())
    assert b.submit("", "hello") is False
    assert b.submit("#alerts", "") is False
    assert b.submit("#alerts", "   ") is False
    assert b.submit("#alerts", None) is False  # type: ignore[arg-type]
    assert b.buffered == 0
    res = b.flush()
    assert res.posted == 0


def test_notifier_failure_is_captured_not_raised():
    n = MockSlackNotifier(fail_on="boom")
    b = SlackBatcher(n, time_fn=FakeClock())
    b.submit("#alerts", "boom event")
    res = b.flush()
    assert res.posted == 0
    assert res.errors == 1
    errs = b.pop_errors()
    assert len(errs) == 1 and isinstance(errs[0], RuntimeError)
    # follow-up call should still work
    b.submit("#alerts", "calm event")
    res2 = b.flush()
    assert res2.posted == 1
    assert b.pop_errors() == []


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        SlackBatcher(MockSlackNotifier(), window_seconds=-1)
    with pytest.raises(ValueError):
        SlackBatcher(MockSlackNotifier(), max_buffer=0)
