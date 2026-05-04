# Track QQ — Webhook HMAC outbound hardening

New `src/webhook_signing.py` — sign_payload returns 3 headers
(timestamp + nonce + HMAC-SHA256). verify_request rejects tampered,
stale (>5min), and replayed requests via in-memory NonceCache.

6 tests pass. Pure stdlib, no new dep.
