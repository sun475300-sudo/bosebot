"""Flask admin endpoints for the law auto-updater.

Wires two routes:
  - ``GET /api/admin/law-sync/status`` — current updater status.
  - ``POST /api/admin/law-sync/refresh`` — trigger one sync cycle.

Authentication
--------------
By default the routes require ``Authorization: Bearer <ADMIN_TOKEN>`` where
``ADMIN_TOKEN`` is read from the environment. Pass a custom decorator via
``auth_required`` to integrate with an existing admin-auth scheme.

Usage::

    from src.law_sync_admin import register_law_sync_routes
    register_law_sync_routes(app)            # uses ADMIN_TOKEN env var
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Callable, Optional

from src.law_auto_updater import (
    LawAutoUpdater,
    get_auto_updater,
    start_auto_updater,
)


def _default_admin_token_auth(f: Callable) -> Callable:
    """Default ``Authorization: Bearer <ADMIN_TOKEN>`` guard.

    If ``ADMIN_TOKEN`` env var is unset, the route is locked: every call
    returns 503 so an operator can\'t accidentally expose the endpoint.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import jsonify, request
        token = os.environ.get("ADMIN_TOKEN", "").strip()
        if not token:
            return jsonify({
                "error": "ADMIN_TOKEN env var not configured; endpoint disabled",
            }), 503
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Authorization header required"}), 401
        if header[7:].strip() != token:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def register_law_sync_routes(
    app,
    *,
    auth_required: Optional[Callable] = None,
    on_change: Optional[Callable] = None,
) -> None:
    """Mount law-sync admin routes onto a Flask ``app``.

    Parameters
    ----------
    app : flask.Flask
    auth_required : callable, optional
        Decorator factory. Defaults to :func:`_default_admin_token_auth`.
    on_change : callable, optional
        Forwarded to :func:`start_auto_updater` when ``/refresh`` triggers
        a fresh updater (only used if no singleton exists yet).
    """
    from flask import jsonify, request  # noqa: F401  (request reserved)

    auth = auth_required or _default_admin_token_auth

    @app.route("/api/admin/law-sync/status", methods=["GET"])
    @auth
    def _law_sync_status():
        upd = get_auto_updater()
        if upd is None:
            return jsonify({
                "enabled": False,
                "running": False,
                "message": "no auto-updater singleton; "
                           "either disabled or never started",
            })
        return jsonify(upd.status())

    @app.route("/api/admin/law-sync/refresh", methods=["POST"])
    @auth
    def _law_sync_refresh():
        upd = get_auto_updater()
        if upd is None:
            # Lazy: build a one-off updater for this manual call so the
            # endpoint still works even when the background scheduler is
            # disabled.
            upd = LawAutoUpdater(enabled=True, on_change=on_change)
        result = upd.run_once()
        return jsonify(result)
