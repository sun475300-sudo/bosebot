"""WebSocket server (Track CC) — bidirectional chat + typing indicator + presence.

This module is OPTIONAL. If the `websockets` library is not installed,
`HAS_WS` is False and `start_ws_server()` raises RuntimeError. The web
application keeps working (SSE streaming and HTTP fall back).

Protocol (JSON over WebSocket frames):
    Client → Server:
        {"type": "auth", "token": "<jwt>"}
        {"type": "typing", "session_id": "..."}
        {"type": "chat",   "session_id": "...", "text": "..."}
        {"type": "ping"}
    Server → Client:
        {"type": "auth_ok",  "user_id": "...", "presence": ["..."]}
        {"type": "typing",   "user_id": "..."}
        {"type": "presence", "online": [...], "joined": "...", "left": "..."}
        {"type": "chat_partial", "delta": "..."}
        {"type": "chat_end",     "answer": "...", "ms": 123}
        {"type": "pong"}
        {"type": "error", "message": "..."}

Run standalone:
    python -m src.ws_server   # listens on :8765 by default
or via ``scripts/run_ws.py``. Place behind a reverse proxy (nginx, traefik).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)

try:
    import websockets  # type: ignore
    from websockets.server import WebSocketServerProtocol  # type: ignore

    HAS_WS = True
except Exception:  # pragma: no cover - optional dependency
    websockets = None  # type: ignore
    WebSocketServerProtocol = Any  # type: ignore
    HAS_WS = False


# ---------------------------------------------------------------------------
# Connection registry — small, stdlib only, easily mockable.
# ---------------------------------------------------------------------------


class ConnectionRegistry:
    """Tracks live websocket connections with a tiny presence model."""

    def __init__(self) -> None:
        self._conns: Dict[str, Set[Any]] = {}  # user_id -> ws set

    def add(self, user_id: str, ws: Any) -> None:
        self._conns.setdefault(user_id, set()).add(ws)

    def remove(self, user_id: str, ws: Any) -> None:
        bucket = self._conns.get(user_id)
        if not bucket:
            return
        bucket.discard(ws)
        if not bucket:
            self._conns.pop(user_id, None)

    def online(self) -> list[str]:
        return sorted(self._conns.keys())

    def peers(self, user_id: str) -> list[Any]:
        return list(self._conns.get(user_id, set()))

    def all_peers(self) -> list[Any]:
        flat: list[Any] = []
        for s in self._conns.values():
            flat.extend(s)
        return flat


# ---------------------------------------------------------------------------
# Auth — pluggable callable that turns a token into a user_id.
# ---------------------------------------------------------------------------


def _default_auth(token: Optional[str]) -> Optional[str]:
    """Default auth: any non-empty token is accepted as user_id.

    Real deployments should plug in JWTAuth.verify() or similar.
    """

    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    return token if token else None


# ---------------------------------------------------------------------------
# Message handler — pure function, no I/O. Returns the response payload(s).
# ---------------------------------------------------------------------------


def handle_message(
    msg: Dict[str, Any],
    *,
    user_id: Optional[str],
    registry: "ConnectionRegistry",
    chat_fn: Optional[Callable[[str, str], str]] = None,
    auth_fn: Callable[[Optional[str]], Optional[str]] = _default_auth,
    now: Callable[[], float] = time.time,
) -> Dict[str, Any]:
    """Process a single client message.

    Returns a dict ``{"reply": [...], "broadcast": [...], "user_id": ...}``
    where ``reply`` is sent only to the originating socket, and ``broadcast``
    is delivered to every other socket in the registry. Pure & sync so unit
    tests don't need an event loop.
    """

    mtype = msg.get("type")
    reply: list[Dict[str, Any]] = []
    broadcast: list[Dict[str, Any]] = []
    new_user_id = user_id

    if mtype == "auth":
        uid = auth_fn(msg.get("token"))
        if not uid:
            reply.append({"type": "error", "message": "auth failed"})
        else:
            new_user_id = uid
            registry.add(uid, object())  # placeholder, overwritten by caller
            reply.append({
                "type": "auth_ok",
                "user_id": uid,
                "presence": registry.online(),
            })
            broadcast.append({"type": "presence", "joined": uid, "online": registry.online()})

    elif mtype == "ping":
        reply.append({"type": "pong", "ts": now()})

    elif mtype == "typing":
        if not user_id:
            reply.append({"type": "error", "message": "not authenticated"})
        else:
            broadcast.append({
                "type": "typing",
                "user_id": user_id,
                "session_id": msg.get("session_id"),
            })

    elif mtype == "chat":
        if not user_id:
            reply.append({"type": "error", "message": "not authenticated"})
        else:
            text = (msg.get("text") or "").strip()
            if not text:
                reply.append({"type": "error", "message": "empty text"})
            else:
                start = now()
                try:
                    answer = chat_fn(user_id, text) if chat_fn else f"echo: {text}"
                except Exception as exc:  # pragma: no cover - defensive
                    logger.exception("ws chat handler failed")
                    reply.append({"type": "error", "message": str(exc)})
                else:
                    # Fake a streaming partial then a final frame so the
                    # client's incremental rendering path is exercised even
                    # without a real LLM stream.
                    reply.append({"type": "chat_partial", "delta": answer[: max(1, len(answer) // 2)]})
                    reply.append({
                        "type": "chat_end",
                        "answer": answer,
                        "ms": int((now() - start) * 1000),
                    })

    else:
        reply.append({"type": "error", "message": f"unknown type: {mtype!r}"})

    return {"reply": reply, "broadcast": broadcast, "user_id": new_user_id}


# ---------------------------------------------------------------------------
# Async server bits (only loaded when websockets is installed).
# ---------------------------------------------------------------------------


async def _serve_connection(  # pragma: no cover - exercised via integration
    ws: Any,
    registry: ConnectionRegistry,
    chat_fn: Optional[Callable[[str, str], str]],
) -> None:
    user_id: Optional[str] = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                await ws.send(json.dumps({"type": "error", "message": "invalid json"}))
                continue

            res = handle_message(msg, user_id=user_id, registry=registry, chat_fn=chat_fn)
            user_id = res["user_id"]
            for frame in res["reply"]:
                await ws.send(json.dumps(frame, ensure_ascii=False))
            if res["broadcast"]:
                # Snapshot to avoid mutation during iteration.
                peers = [p for p in registry.all_peers() if p is not ws]
                payloads = [json.dumps(f, ensure_ascii=False) for f in res["broadcast"]]
                await asyncio.gather(
                    *(p.send(p_json) for p in peers for p_json in payloads),
                    return_exceptions=True,
                )
            # Bind the *real* ws into the registry (handle_message used a placeholder).
            if user_id and ws not in registry.peers(user_id):
                # Replace placeholder with actual ws.
                registry._conns[user_id] = {w for w in registry._conns[user_id] if not isinstance(w, object) or hasattr(w, 'send')}
                registry.add(user_id, ws)
    finally:
        if user_id:
            registry.remove(user_id, ws)
            for peer in registry.all_peers():
                try:
                    await peer.send(json.dumps({"type": "presence", "left": user_id, "online": registry.online()}))
                except Exception:
                    pass


async def start_ws_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    chat_fn: Optional[Callable[[str, str], str]] = None,
) -> Any:  # pragma: no cover - network I/O
    """Start the asyncio websocket server. Caller must `await` and `serve_forever`."""

    if not HAS_WS:
        raise RuntimeError(
            "websockets library is not installed; install with `pip install websockets` "
            "or run without the WS server (SSE/HTTP still work)."
        )

    registry = ConnectionRegistry()

    async def _handler(ws):
        await _serve_connection(ws, registry, chat_fn)

    return await websockets.serve(_handler, host, port)


def main() -> int:  # pragma: no cover - CLI entry
    if not HAS_WS:
        print("[ws] websockets library not installed — exit 0 (graceful degrade)")
        return 0
    host = os.environ.get("WS_HOST", "0.0.0.0")
    port = int(os.environ.get("WS_PORT", "8765"))
    logging.basicConfig(level=logging.INFO)

    async def _run():
        server = await start_ws_server(host=host, port=port)
        logger.info("ws server on %s:%s", host, port)
        await server.wait_closed()

    asyncio.run(_run())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
