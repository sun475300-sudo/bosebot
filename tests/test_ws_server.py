"""Tests for Track CC — WebSocket bidirectional + typing indicator."""

from __future__ import annotations

import json

from src import ws_server
from src.ws_server import ConnectionRegistry, handle_message


def test_handle_message_auth_ok():
    reg = ConnectionRegistry()
    out = handle_message({"type": "auth", "token": "alice"}, user_id=None, registry=reg)
    assert out["user_id"] == "alice"
    types = [m["type"] for m in out["reply"]]
    assert "auth_ok" in types
    # Broadcast presence
    assert any(m["type"] == "presence" and m.get("joined") == "alice" for m in out["broadcast"])


def test_handle_message_typing_requires_auth():
    reg = ConnectionRegistry()
    out = handle_message({"type": "typing", "session_id": "s1"}, user_id=None, registry=reg)
    assert out["reply"][0]["type"] == "error"
    # When authed, typing produces broadcast frame
    out2 = handle_message({"type": "typing", "session_id": "s1"}, user_id="bob", registry=reg)
    assert out2["broadcast"][0]["type"] == "typing"
    assert out2["broadcast"][0]["user_id"] == "bob"


def test_handle_message_chat_partial_then_end():
    reg = ConnectionRegistry()
    out = handle_message(
        {"type": "chat", "session_id": "s1", "text": "hello"},
        user_id="alice",
        registry=reg,
        chat_fn=lambda uid, text: f"{uid}:{text.upper()}",
    )
    types = [m["type"] for m in out["reply"]]
    assert types == ["chat_partial", "chat_end"]
    assert out["reply"][1]["answer"] == "alice:HELLO"
    assert isinstance(out["reply"][1]["ms"], int)


def test_handle_message_ping_pong_and_unknown():
    reg = ConnectionRegistry()
    out = handle_message({"type": "ping"}, user_id="x", registry=reg)
    assert out["reply"][0]["type"] == "pong"
    out2 = handle_message({"type": "??"}, user_id="x", registry=reg)
    assert out2["reply"][0]["type"] == "error"


def test_graceful_degrade_when_lib_missing(monkeypatch):
    """If `websockets` is absent, start_ws_server raises a clear RuntimeError."""
    monkeypatch.setattr(ws_server, "HAS_WS", False)
    import asyncio

    async def _run():
        return await ws_server.start_ws_server()

    try:
        asyncio.run(_run())
    except RuntimeError as exc:
        assert "websockets" in str(exc).lower()
    else:
        raise AssertionError("expected RuntimeError when HAS_WS is False")


def test_registry_presence_lifecycle():
    reg = ConnectionRegistry()
    s1 = object()
    s2 = object()
    reg.add("alice", s1)
    reg.add("bob", s2)
    assert set(reg.online()) == {"alice", "bob"}
    reg.remove("alice", s1)
    assert reg.online() == ["bob"]


def test_message_payloads_are_json_serialisable():
    reg = ConnectionRegistry()
    out = handle_message({"type": "auth", "token": "alice"}, user_id=None, registry=reg)
    # Every frame must round-trip through JSON
    for frame in out["reply"] + out["broadcast"]:
        assert json.loads(json.dumps(frame)) == frame
