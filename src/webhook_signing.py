"""Track QQ — outbound webhook signing with timestamp + nonce + HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import OrderedDict
from typing import Dict, Optional, Tuple

SIGNATURE_VERSION = "v1"
DEFAULT_REPLAY_WINDOW = 300


def _canonical(timestamp: str, nonce: str, body: bytes) -> bytes:
    return b"\n".join([timestamp.encode("ascii"), nonce.encode("ascii"), body])


def sign_payload(secret: str, body, *, now: Optional[float] = None, nonce: Optional[str] = None) -> Dict[str, str]:
    if not secret:
        raise ValueError("secret required")
    if isinstance(body, str):
        body = body.encode("utf-8")
    ts = str(int(now if now is not None else time.time()))
    n = nonce or secrets.token_hex(16)
    mac = hmac.new(secret.encode("utf-8"), _canonical(ts, n, body), hashlib.sha256).hexdigest()
    return {
        "X-Webhook-Timestamp": ts,
        "X-Webhook-Nonce": n,
        "X-Webhook-Signature": f"{SIGNATURE_VERSION}={mac}",
    }


class NonceCache:
    def __init__(self, ttl_seconds: int = DEFAULT_REPLAY_WINDOW, capacity: int = 8192):
        self._ttl = ttl_seconds
        self._cap = capacity
        self._lock = threading.Lock()
        self._items: OrderedDict[str, float] = OrderedDict()

    def add_if_unseen(self, nonce: str, *, now: Optional[float] = None) -> bool:
        ts = now if now is not None else time.time()
        with self._lock:
            self._gc(ts)
            if nonce in self._items:
                return False
            self._items[nonce] = ts
            if len(self._items) > self._cap:
                self._items.popitem(last=False)
            return True

    def _gc(self, ts: float) -> None:
        cutoff = ts - self._ttl
        while self._items:
            k, t = next(iter(self._items.items()))
            if t < cutoff:
                self._items.pop(k, None)
            else:
                break

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


_default_cache = NonceCache()


def verify_request(secret: str, body, headers: Dict[str, str], *, now: Optional[float] = None,
                   replay_window: int = DEFAULT_REPLAY_WINDOW, nonce_cache: Optional[NonceCache] = None) -> Tuple[bool, str]:
    if not secret:
        return False, "bad_secret"
    if isinstance(body, str):
        body = body.encode("utf-8")
    cache = nonce_cache if nonce_cache is not None else _default_cache
    ts = headers.get("X-Webhook-Timestamp") or headers.get("x-webhook-timestamp")
    nonce = headers.get("X-Webhook-Nonce") or headers.get("x-webhook-nonce")
    sig = headers.get("X-Webhook-Signature") or headers.get("x-webhook-signature")
    if not (ts and nonce and sig):
        return False, "missing_header"
    try:
        ts_int = int(ts)
    except ValueError:
        return False, "missing_header"
    current = now if now is not None else time.time()
    if abs(current - ts_int) > replay_window:
        return False, "stale"
    if "=" not in sig:
        return False, "bad_signature"
    version, hex_mac = sig.split("=", 1)
    if version != SIGNATURE_VERSION:
        return False, "bad_signature"
    expected = hmac.new(secret.encode("utf-8"), _canonical(ts, nonce, body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, hex_mac):
        return False, "bad_signature"
    if not cache.add_if_unseen(nonce, now=current):
        return False, "replay"
    return True, ""
