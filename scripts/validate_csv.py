#!/usr/bin/env python3
"""Track UU — CSV schema validator CLI.

Usage:
    python scripts/validate_csv.py --schema config/csv_schemas/faq.json data/faq.csv [data/more.csv ...]

Exit codes:
    0 — all files valid
    1 — at least one file failed validation
    2 — script error
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.csv_validator import load_schema_json, validate_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CSVs against a schema")
    parser.add_argument("--schema", required=True, help="path to schema JSON")
    parser.add_argument("paths", nargs="+", help="CSV files to validate")
    parser.add_argument("--max-errors", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        print(f"[csv-validate] schema not found: {args.schema}", file=sys.stderr)
        return 2
    schema = load_schema_json(args.schema)

    failures = []
    summary = []
    for p in args.paths:
        if not os.path.exists(p):
            failures.append(p)
            summary.append({"path": p, "ok": False, "errors": ["file not found"]})
            print(f"FAIL  {p} — file not found")
            continue
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        report = validate_csv(text, schema, max_errors=args.max_errors)
        summary.append({
            "path": p,
            "ok": report.ok,
            "rows_checked": report.rows_checked,
            "errors": report.errors,
        })
        if report.ok:
            print(f"OK    {p} — {report.rows_checked} rows")
        else:
            failures.append(p)
            print(f"FAIL  {p} — {len(report.errors)} error(s):")
            for e in report.errors[:20]:
                print(f"        {e}")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
