"""slack_batcher - Batching + dedup wrapper around any Slack-like notifier (WW).

Goal: prevent message storms when many alerts fire in a short window.

Behaviour
---------
* Caller submits messages via :meth:`SlackBatcher.submit`.
* Within ``window_seconds``, identical messages (same channel + content hash)
  collapse to a single delivery, with a ``(xN)`` suffix.
* Distinct messages collected during the window are flushed together as one
  combined post (joined with ``\n``).
* :meth:`flush` is called automatically when the window elapses (driven by
  the caller's clock — see ``time_fn``) or when ``max_buffer`` is exceeded.
* Underlying notifier is any callable ``notifier(channel, text) -> bool``.
  A failing notifier raises; ``submit``/``flush`` swallow exceptions and
  surface them via :meth:`pop_errors` so the caller never crashes.

External deps: none. The module only relies on stdlib.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable


def _hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:12]


@dataclass
class _Bucket:
    """Per-(channel, hash) accumulator inside the active window."""

    channel: str
    text: str
    count: int = 1
    first_seen: float = 0.0


@dataclass
class FlushResult:
    """Return type of :meth:`SlackBatcher.flush`."""

    posted: int = 0
    suppressed: int = 0
    errors: int = 0
    channels: list[str] = field(default_factory=list)


class MockSlackNotifier:
    """Test double — records every (channel, text) it would have posted."""

    def __init__(self, fail_on: str | None = None):
        self.posts: list[tuple[str, str]] = []
        self.fail_on = fail_on

    def __call__(self, channel: str, text: str) -> bool:
        if self.fail_on and self.fail_on in text:
            raise RuntimeError(f"slack mock failure: {self.fail_on}")
        self.posts.append((channel, text))
        return True


class SlackBatcher:
    """Window-based batcher with content-hash dedup."""

    def __init__(
        self,
        notifier: Callable[[str, str], bool],
        window_seconds: float = 5.0,
        max_buffer: int = 50,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        if window_seconds < 0:
            raise ValueError("window_seconds must be >= 0")
        if max_buffer < 1:
            raise ValueError("max_buffer must be >= 1")
        self.notifier = notifier
        self.window = float(window_seconds)
        self.max_buffer = int(max_buffer)
        self._now = time_fn
        self._buf: "OrderedDict[tuple[str, str], _Bucket]" = OrderedDict()
        self._window_start: float | None = None
        self._lock = threading.Lock()
        self._errors: list[Exception] = []

    # -- public ---------------------------------------------------------

    @property
    def buffered(self) -> int:
        with self._lock:
            return len(self._buf)

    def submit(self, channel: str, text: str) -> bool:
        """Add a message. Returns True if accepted, False if dropped (empty)."""
        if not channel or text is None:
            return False
        text = text.strip()
        if not text:
            return False

        with self._lock:
            now = self._now()
            window_elapsed = (
                self._window_start is not None
                and self.window
                and (now - self._window_start) >= self.window
                and bool(self._buf)
            )

        if window_elapsed:
            self.flush()

        flush_now = False
        with self._lock:
            now = self._now()
            if self._window_start is None:
                self._window_start = now

            key = (channel, _hash(text))
            bucket = self._buf.get(key)
            if bucket is None:
                self._buf[key] = _Bucket(
                    channel=channel, text=text, count=1, first_seen=now
                )
            else:
                bucket.count += 1

            if len(self._buf) >= self.max_buffer:
                flush_now = True

        if flush_now:
            self.flush()
        return True

    def flush(self) -> FlushResult:
        """Send all buffered messages, grouped by channel. Always safe to call."""
        with self._lock:
            buckets = list(self._buf.values())
            self._buf.clear()
            self._window_start = None

        result = FlushResult()
        if not buckets:
            return result

        # Group by channel preserving submit order.
        by_channel: "OrderedDict[str, list[_Bucket]]" = OrderedDict()
        for b in buckets:
            by_channel.setdefault(b.channel, []).append(b)

        for channel, items in by_channel.items():
            lines = []
            channel_suppressed = 0
            for b in items:
                line = b.text if b.count == 1 else f"{b.text}  (x{b.count})"
                lines.append(line)
                channel_suppressed += max(0, b.count - 1)
            payload = "\n".join(lines)
            try:
                self.notifier(channel, payload)
                result.posted += 1
                result.suppressed += channel_suppressed
                result.channels.append(channel)
            except Exception as exc:  # graceful — never crash the caller
                self._errors.append(exc)
                result.errors += 1
        return result

    def pop_errors(self) -> list[Exception]:
        """Return and clear any errors captured during prior flushes."""
        with self._lock:
            errs = list(self._errors)
            self._errors.clear()
        return errs

    # -- helpers --------------------------------------------------------

    def force_window_elapsed(self) -> None:
        """Test helper: pretend the window has fully elapsed."""
        with self._lock:
            self._window_start = None


__all__ = [
    "FlushResult",
    "MockSlackNotifier",
    "SlackBatcher",
]
