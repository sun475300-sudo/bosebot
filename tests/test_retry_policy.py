"""Tests for src/retry_policy.py — retry with exponential backoff + jitter."""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retry_policy import RetryPolicy, retry


def test_policy_defaults_validate():
    p = RetryPolicy()
    assert p.max_attempts == 3
    assert p.base_delay == 0.5
    assert p.max_delay >= p.base_delay


def test_policy_rejects_invalid_max_attempts():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)


def test_policy_rejects_invalid_jitter():
    with pytest.raises(ValueError):
        RetryPolicy(jitter=1.5)


def test_compute_delay_grows_exponentially_without_jitter():
    p = RetryPolicy(base_delay=0.1, backoff_factor=2.0, jitter=0.0, max_delay=10)
    assert p.compute_delay(1) == pytest.approx(0.1)
    assert p.compute_delay(2) == pytest.approx(0.2)
    assert p.compute_delay(3) == pytest.approx(0.4)
    assert p.compute_delay(10) <= p.max_delay


def test_compute_delay_jitter_within_bounds():
    p = RetryPolicy(base_delay=1.0, backoff_factor=1.0, jitter=0.5, max_delay=10)
    samples = [p.compute_delay(1) for _ in range(50)]
    assert all(0.5 <= s <= 1.5 for s in samples)


def test_should_retry_respects_give_up_on():
    p = RetryPolicy(retry_on=(Exception,), give_up_on=(KeyError,))
    assert p.should_retry(ValueError("x")) is True
    assert p.should_retry(KeyError("x")) is False


def test_run_succeeds_first_try():
    p = RetryPolicy(max_attempts=3, base_delay=0)
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    assert p.run(fn) == "ok"
    assert len(calls) == 1


def test_run_retries_until_success():
    p = RetryPolicy(max_attempts=4, base_delay=0)
    counter = {"n": 0}

    def flaky():
        counter["n"] += 1
        if counter["n"] < 3:
            raise RuntimeError("transient")
        return "done"

    assert p.run(flaky) == "done"
    assert counter["n"] == 3


def test_run_raises_after_max_attempts():
    p = RetryPolicy(max_attempts=2, base_delay=0)

    def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        p.run(always_fail)


def test_run_does_not_retry_for_give_up_on():
    p = RetryPolicy(max_attempts=5, base_delay=0, give_up_on=(KeyError,))
    counter = {"n": 0}

    def fail():
        counter["n"] += 1
        raise KeyError("hard fail")

    with pytest.raises(KeyError):
        p.run(fail)
    assert counter["n"] == 1


def test_on_retry_callback_called():
    events = []

    def hook(attempt, exc, delay):
        events.append((attempt, type(exc).__name__))

    p = RetryPolicy(max_attempts=3, base_delay=0, on_retry=hook)

    def fail():
        raise ValueError("x")

    with pytest.raises(ValueError):
        p.run(fail)
    assert events == [(1, "ValueError"), (2, "ValueError")]


def test_decorator_with_kwargs():
    @retry(max_attempts=3, base_delay=0)
    def flaky():
        flaky.calls += 1
        if flaky.calls < 2:
            raise RuntimeError("retry me")
        return "ok"
    flaky.calls = 0

    assert flaky() == "ok"
    assert flaky.calls == 2
    assert flaky.__retry_policy__.max_attempts == 3


def test_decorator_with_explicit_policy_object():
    p = RetryPolicy(max_attempts=2, base_delay=0)

    @retry(p)
    def boom():
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        boom()


def test_decorator_raises_if_both_policy_and_kwargs():
    with pytest.raises(TypeError):
        retry(RetryPolicy(), max_attempts=5)
