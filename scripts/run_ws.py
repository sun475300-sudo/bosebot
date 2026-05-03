#!/usr/bin/env python3
"""Run the optional WebSocket server (Track CC).

Usage:
    python scripts/run_ws.py [--host 0.0.0.0] [--port 8765]

If the `websockets` library is not installed, this script exits 0 with a
notice — letting deployments stay green even when WS is not enabled.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ws_server import HAS_WS, start_ws_server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional WS server")
    parser.add_argument("--host", default=os.environ.get("WS_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WS_PORT", "8765")))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not HAS_WS:
        print("[ws] `websockets` not installed — skip (exit 0)")
        return 0

    async def _run():
        server = await start_ws_server(host=args.host, port=args.port)
        logging.info("WS server up on %s:%s", args.host, args.port)
        await server.wait_closed()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
