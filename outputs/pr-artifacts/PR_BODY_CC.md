# Track CC — WebSocket bidirectional + typing indicator (graceful degrade)

## What

- New optional WebSocket server (`src/ws_server.py`) — bidirectional
  chat, typing indicator, presence broadcast, ping/pong.
- Pure-function message handler (`handle_message`) — no I/O, easy unit-test.
- Standalone runner (`scripts/run_ws.py`) for reverse-proxy deployments.
- **Graceful degrade**: if `websockets` library is not installed,
  `HAS_WS` is False and `start_ws_server()` raises a clear RuntimeError.
  Existing SSE / HTTP paths keep working — no breakage.

## Why

Adds a low-latency channel for typing indicator and presence without
forcing a hard dependency on `websockets` in the base image.

## Tests

`tests/test_ws_server.py` — 7 tests, all pass:

- auth handshake produces `auth_ok` + presence broadcast
- `typing` requires auth, otherwise emits error
- `chat` produces partial then end with timing
- ping/pong + unknown-type error
- registry presence add/remove lifecycle
- payloads are JSON-serialisable
- monkey-patched `HAS_WS=False` → RuntimeError surfaces

```
tests/test_ws_server.py .......                                          [100%]
7 passed in 0.13s
```

## Risk

- Optional dependency; default builds unchanged.
- No mutation of existing routes.

## Rollback

- `git revert <merge-sha>` — single-commit, isolated module.
