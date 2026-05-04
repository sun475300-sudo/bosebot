"""External-scheduler entrypoint for the law auto-updater.

Designed to be invoked by Windows Task Scheduler / cron when the in-app
background scheduler is disabled (``LAW_AUTO_UPDATE_ENABLED=false``).

Each invocation runs exactly **one** sync cycle (admRul + law) and exits.

Usage::

    python scripts/scheduled_refresh.py
    python scripts/scheduled_refresh.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.law_auto_updater import LawAutoUpdater  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a single law/admrul sync cycle "
                    "(for cron / Task Scheduler).",
    )
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of human-readable lines")
    args = parser.parse_args()

    # Force enable for this single run regardless of LAW_AUTO_UPDATE_ENABLED
    updater = LawAutoUpdater(enabled=True)
    result = updater.run_once()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = result.get("status")
        changes = result.get("changes_detected")
        err = result.get("error")
        print("status: " + str(status))
        print("changes_detected: " + str(changes))
        if err:
            print("error: " + str(err))
        admrul = result.get("admrul") or {}
        for d in admrul.get("details", []):
            name = d.get("name", "")
            seq = d.get("admrul_seq", "")
            stat = d.get("status", "")
            print("  - " + name + " (" + seq + "): " + stat)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
