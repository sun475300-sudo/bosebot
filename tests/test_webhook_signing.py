"""Tests for Track QQ — webhook HMAC signing + replay protection."""
import time
import pytest
from src.webhook_signing import NonceCache, sign_payload, verify_request

SECRET = "s3cret-rotated-monthly"


def test_sign_then_verify_roundtrip():
    body = b'{"event": "ping"}'
    h = sign_payload(SECRET, body)
    ok, why = verify_request(SECRET, body, h, nonce_cache=NonceCache())
    assert ok and why == ""


def test_tampered_body_fails():
    h = sign_payload(SECRET, b"original")
    ok, why = verify_request(SECRET, b"tampered", h, nonce_cache=NonceCache())
    assert not ok and why == "bad_signature"


def test_stale_timestamp_rejected():
    h = sign_payload(SECRET, b"hi", now=time.time() - 600)
    ok, why = verify_request(SECRET, b"hi", h, nonce_cache=NonceCache())
    assert not ok and why == "stale"


def test_replay_attack_rejected():
    cache = NonceCache()
    h = sign_payload(SECRET, b"hi")
    ok, _ = verify_request(SECRET, b"hi", h, nonce_cache=cache)
    assert ok
    ok2, why = verify_request(SECRET, b"hi", h, nonce_cache=cache)
    assert not ok2 and why == "replay"


def test_missing_header_and_bad_secret():
    h = sign_payload(SECRET, b"hi")
    ok, why = verify_request(SECRET, b"hi", {"X-Webhook-Signature": h["X-Webhook-Signature"]}, nonce_cache=NonceCache())
    assert not ok and why == "missing_header"
    ok2, why2 = verify_request("", b"hi", h, nonce_cache=NonceCache())
    assert not ok2 and why2 == "bad_secret"


def test_nonce_cache_gc():
    cache = NonceCache(ttl_seconds=1)
    cache.add_if_unseen("a", now=1000.0)
    cache.add_if_unseen("b", now=1000.0)
    assert len(cache) == 2
    cache.add_if_unseen("c", now=2000.0)
    assert len(cache) == 1
