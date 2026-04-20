"""Answer accuracy benchmark using a golden test set.

Evaluates the chatbot's classification and FAQ matching accuracy by running
every test case in a golden test set file through BondedExhibitionChatbot
and comparing the predicted category / FAQ id with the expected values.

Typical usage::

    bench = AccuracyBenchmark()
    metrics = bench.run_benchmark("data/golden_testset.json")
    bench.export_report(metrics, "reports/accuracy.html")

The module also exposes history persistence so results can be compared
over time via :meth:`AccuracyBenchmark.compare_results`.
"""

from __future__ import annotations

import html as _html
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Iterable

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Some golden test sets use forward-looking category names that alias to the
# codes that actually exist in the chatbot configuration. Keep the mapping in
# one place so both sides can stay readable.
DEFAULT_CATEGORY_ALIASES: dict[str, str] = {
    "DISPLAY_USE": "EXHIBITION",
}


class AccuracyBenchmark:
    """Run and track the answer-accuracy benchmark.

    Args:
        chatbot: Optional pre-built chatbot. When ``None`` a new instance of
            :class:`src.chatbot.BondedExhibitionChatbot` is created on demand.
        history_db: Path to a SQLite database for storing benchmark history.
            Defaults to ``logs/accuracy_benchmark.db``.
    """

    def __init__(self, chatbot: Any = None, history_db: str | None = None) -> None:
        self._chatbot = chatbot
        if history_db is None:
            history_db = os.path.join(BASE_DIR, "logs", "accuracy_benchmark.db")
        self.history_db = history_db
        os.makedirs(os.path.dirname(self.history_db), exist_ok=True)
        self._init_history_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_benchmark(
        self,
        testset_path: str,
        persist: bool = True,
        category_aliases: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run the benchmark against ``testset_path`` and return metrics.

        Args:
            testset_path: Path to the golden testset JSON file. May be absolute
                or relative to the project root.
            persist: When ``True`` the result is saved into the history db.
            category_aliases: Optional mapping of forward-looking category
                names in the testset to the codes emitted by the chatbot.
                When ``None`` the file's ``category_aliases`` key is used and
                falls back to :data:`DEFAULT_CATEGORY_ALIASES`.

        Returns:
            A metrics dictionary of the form::

                {
                    "total": 100,
                    "correct_category": 85,
                    "correct_faq": 72,
                    "category_accuracy": 0.85,
                    "faq_accuracy": 0.72,
                    "by_category": {"GENERAL": {"total": 10, ...}, ...},
                    "failures": [{"question": str, "expected": str, ...}],
                    "testset_path": str,
                    "testset_version": str,
                    "timestamp": str,
                    "duration_sec": float,
                }
        """
        testset = self._load_testset(testset_path)
        items = testset.get("items", [])
        aliases = dict(DEFAULT_CATEGORY_ALIASES)
        aliases.update(testset.get("category_aliases", {}) or {})
        if category_aliases:
            aliases.update(category_aliases)

        chatbot = self._get_chatbot()

        total = len(items)
        correct_category = 0
        correct_faq = 0
        by_category: dict[str, dict[str, int]] = {}
        failures: list[dict[str, Any]] = []

        start = time.time()
        for idx, case in enumerate(items):
            question = case.get("question", "")
            expected_category_raw = case.get("expected_category", "")
            expected_category = aliases.get(expected_category_raw, expected_category_raw)
            expected_faq = case.get("expected_faq_id", "")

            actual_category, actual_faq = self._classify_case(chatbot, question)

            cat_ok = bool(expected_category) and actual_category == expected_category
            faq_ok = bool(expected_faq) and actual_faq == expected_faq

            if cat_ok:
                correct_category += 1
            if faq_ok:
                correct_faq += 1

            bucket = by_category.setdefault(
                expected_category_raw,
                {"total": 0, "correct_category": 0, "correct_faq": 0},
            )
            bucket["total"] += 1
            if cat_ok:
                bucket["correct_category"] += 1
            if faq_ok:
                bucket["correct_faq"] += 1

            if not cat_ok or not faq_ok:
                failures.append({
                    "index": idx,
                    "question": question,
                    "type": case.get("type", "unspecified"),
                    "expected": {
                        "category": expected_category_raw,
                        "faq_id": expected_faq,
                    },
                    "actual": {
                        "category": actual_category,
                        "faq_id": actual_faq,
                    },
                    "category_ok": cat_ok,
                    "faq_ok": faq_ok,
                })

        duration = time.time() - start

        for stats in by_category.values():
            t = max(stats["total"], 1)
            stats["category_accuracy"] = round(stats["correct_category"] / t, 4)
            stats["faq_accuracy"] = round(stats["correct_faq"] / t, 4)
            stats["accuracy"] = stats["category_accuracy"]

        metrics: dict[str, Any] = {
            "total": total,
            "correct_category": correct_category,
            "correct_faq": correct_faq,
            "category_accuracy": round(correct_category / total, 4) if total else 0.0,
            "faq_accuracy": round(correct_faq / total, 4) if total else 0.0,
            "by_category": by_category,
            "failures": failures,
            "testset_path": testset_path,
            "testset_version": testset.get("version", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "duration_sec": round(duration, 3),
        }

        if persist:
            try:
                self._save_history(metrics)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Failed to persist benchmark result: %s", e)

        return metrics

    def compare_results(
        self,
        current: dict[str, Any],
        previous: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Compare two benchmark runs and flag regressions.

        Args:
            current: Metrics returned by :meth:`run_benchmark`.
            previous: Previous metrics to compare against. When ``None`` the
                comparison reports no regression.

        Returns:
            Dict with keys ``regression`` (bool), ``category_delta``,
            ``faq_delta``, ``regressed_categories`` and ``summary``.
        """
        if not previous:
            return {
                "regression": False,
                "category_delta": 0.0,
                "faq_delta": 0.0,
                "regressed_categories": [],
                "summary": "no previous result to compare",
            }

        cat_delta = round(current.get("category_accuracy", 0.0) - previous.get("category_accuracy", 0.0), 4)
        faq_delta = round(current.get("faq_accuracy", 0.0) - previous.get("faq_accuracy", 0.0), 4)

        regressed: list[dict[str, Any]] = []
        prev_by_cat = previous.get("by_category", {}) or {}
        for cat, stats in (current.get("by_category", {}) or {}).items():
            prev_stats = prev_by_cat.get(cat)
            if not prev_stats:
                continue
            delta = round(stats.get("category_accuracy", 0.0) - prev_stats.get("category_accuracy", 0.0), 4)
            faq_d = round(stats.get("faq_accuracy", 0.0) - prev_stats.get("faq_accuracy", 0.0), 4)
            if delta < 0 or faq_d < 0:
                regressed.append({
                    "category": cat,
                    "category_delta": delta,
                    "faq_delta": faq_d,
                })

        regression = cat_delta < 0 or faq_delta < 0 or bool(regressed)

        summary = (
            f"category Δ={cat_delta:+.4f}, faq Δ={faq_delta:+.4f}; "
            f"{len(regressed)} category regression(s)"
        )

        return {
            "regression": regression,
            "category_delta": cat_delta,
            "faq_delta": faq_delta,
            "regressed_categories": regressed,
            "summary": summary,
        }

    def export_report(self, metrics: dict[str, Any], output_path: str) -> str:
        """Render ``metrics`` as a standalone HTML report.

        Args:
            metrics: Metrics dict produced by :meth:`run_benchmark`.
            output_path: Target HTML file path. Parent directories are
                created automatically.

        Returns:
            The absolute path to the written file.
        """
        if not os.path.isabs(output_path):
            output_path = os.path.join(BASE_DIR, output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        html_body = self._render_html(metrics)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        return output_path

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent benchmark runs from the history db."""
        with sqlite3.connect(self.history_db) as conn:
            cur = conn.execute(
                "SELECT id, timestamp, total, correct_category, correct_faq, "
                "category_accuracy, faq_accuracy, testset_path, testset_version, "
                "duration_sec, metrics_json "
                "FROM benchmark_runs ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            rows = cur.fetchall()

        history = []
        for row in rows:
            (run_id, ts, total, cc, cf, ca, fa, tp, tv, dur, metrics_json) = row
            entry = {
                "id": run_id,
                "timestamp": ts,
                "total": total,
                "correct_category": cc,
                "correct_faq": cf,
                "category_accuracy": ca,
                "faq_accuracy": fa,
                "testset_path": tp,
                "testset_version": tv,
                "duration_sec": dur,
            }
            if metrics_json:
                try:
                    entry["metrics"] = json.loads(metrics_json)
                except json.JSONDecodeError:
                    pass
            history.append(entry)
        return history

    def get_latest(self) -> dict[str, Any] | None:
        """Return the most recent benchmark result, if any."""
        rows = self.get_history(limit=1)
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_chatbot(self) -> Any:
        if self._chatbot is None:
            from src.chatbot import BondedExhibitionChatbot
            self._chatbot = BondedExhibitionChatbot()
        return self._chatbot

    def _load_testset(self, testset_path: str) -> dict[str, Any]:
        path = testset_path
        if not os.path.isabs(path):
            candidate = os.path.join(BASE_DIR, path)
            if os.path.exists(candidate):
                path = candidate
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "items" not in data:
            raise ValueError(
                "Golden testset must be a JSON object with an 'items' array"
            )
        return data

    def _classify_case(self, chatbot: Any, question: str) -> tuple[str, str]:
        """Return (predicted_category, predicted_faq_id) for ``question``."""
        try:
            result = chatbot.process_query(question, include_metadata=True)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Chatbot failed on question '%s': %s", question, e)
            return ("UNKNOWN", "")

        if isinstance(result, dict):
            category = result.get("category", "UNKNOWN") or "UNKNOWN"
        else:
            category = "UNKNOWN"

        # FAQ id is not directly included in the result metadata, so run the
        # matching pipeline separately using the predicted category.
        faq_id = ""
        try:
            faq_match = chatbot.find_matching_faq(question, category)
            if isinstance(faq_match, dict):
                faq_id = faq_match.get("id", "") or ""
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("FAQ lookup failed for '%s': %s", question, e)

        return (category, faq_id)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _init_history_db(self) -> None:
        with sqlite3.connect(self.history_db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    correct_category INTEGER NOT NULL,
                    correct_faq INTEGER NOT NULL,
                    category_accuracy REAL NOT NULL,
                    faq_accuracy REAL NOT NULL,
                    testset_path TEXT,
                    testset_version TEXT,
                    duration_sec REAL,
                    metrics_json TEXT
                )
                """
            )
            conn.commit()

    def _save_history(self, metrics: dict[str, Any]) -> int:
        with sqlite3.connect(self.history_db) as conn:
            cur = conn.execute(
                """
                INSERT INTO benchmark_runs (
                    timestamp, total, correct_category, correct_faq,
                    category_accuracy, faq_accuracy, testset_path,
                    testset_version, duration_sec, metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics.get("timestamp"),
                    metrics.get("total", 0),
                    metrics.get("correct_category", 0),
                    metrics.get("correct_faq", 0),
                    metrics.get("category_accuracy", 0.0),
                    metrics.get("faq_accuracy", 0.0),
                    metrics.get("testset_path"),
                    metrics.get("testset_version"),
                    metrics.get("duration_sec"),
                    json.dumps(metrics, ensure_ascii=False),
                ),
            )
            conn.commit()
            return cur.lastrowid or 0

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------
    @staticmethod
    def _pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    def _render_html(self, metrics: dict[str, Any]) -> str:
        esc = _html.escape
        by_cat_rows: list[str] = []
        for cat, stats in sorted(metrics.get("by_category", {}).items()):
            by_cat_rows.append(
                "<tr>"
                f"<td>{esc(str(cat))}</td>"
                f"<td>{stats.get('total', 0)}</td>"
                f"<td>{stats.get('correct_category', 0)}</td>"
                f"<td>{stats.get('correct_faq', 0)}</td>"
                f"<td>{self._pct(stats.get('category_accuracy', 0.0))}</td>"
                f"<td>{self._pct(stats.get('faq_accuracy', 0.0))}</td>"
                "</tr>"
            )

        failure_rows: list[str] = []
        for fail in metrics.get("failures", []):
            exp = fail.get("expected", {})
            act = fail.get("actual", {})
            failure_rows.append(
                "<tr>"
                f"<td>{fail.get('index', '')}</td>"
                f"<td>{esc(fail.get('question', ''))}</td>"
                f"<td>{esc(fail.get('type', ''))}</td>"
                f"<td>{esc(str(exp.get('category', '')))} / {esc(str(exp.get('faq_id', '')))}</td>"
                f"<td>{esc(str(act.get('category', '')))} / {esc(str(act.get('faq_id', '')))}</td>"
                "</tr>"
            )

        by_cat_table = (
            "<table><thead><tr><th>Category</th><th>Total</th>"
            "<th>Correct Category</th><th>Correct FAQ</th>"
            "<th>Category Acc</th><th>FAQ Acc</th></tr></thead>"
            f"<tbody>{''.join(by_cat_rows) or '<tr><td colspan=6>(no data)</td></tr>'}</tbody></table>"
        )

        failure_table = (
            "<table><thead><tr><th>#</th><th>Question</th><th>Type</th>"
            "<th>Expected (cat / faq)</th><th>Actual (cat / faq)</th></tr></thead>"
            f"<tbody>{''.join(failure_rows) or '<tr><td colspan=5>No failures</td></tr>'}</tbody></table>"
        )

        return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>Accuracy Benchmark Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #222; }}
h1 {{ margin-bottom: 4px; }}
.summary {{ margin: 16px 0; padding: 12px; background: #f5f7fa; border-radius: 6px; }}
.summary span {{ display: inline-block; margin-right: 24px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
th, td {{ border: 1px solid #d5d9e0; padding: 6px 10px; text-align: left; vertical-align: top; }}
th {{ background: #eef1f5; }}
.pct-good {{ color: #107c10; }}
.pct-bad {{ color: #c0392b; }}
</style>
</head>
<body>
<h1>Answer Accuracy Benchmark Report</h1>
<div class=\"summary\">
  <span><strong>Timestamp:</strong> {esc(str(metrics.get('timestamp', '')))}</span>
  <span><strong>Testset:</strong> {esc(str(metrics.get('testset_path', '')))} (v{esc(str(metrics.get('testset_version', 'unknown')))})</span>
  <span><strong>Duration:</strong> {metrics.get('duration_sec', 0)}s</span>
</div>
<div class=\"summary\">
  <span><strong>Total:</strong> {metrics.get('total', 0)}</span>
  <span><strong>Correct Category:</strong> {metrics.get('correct_category', 0)}</span>
  <span><strong>Correct FAQ:</strong> {metrics.get('correct_faq', 0)}</span>
  <span><strong>Category Accuracy:</strong> {self._pct(metrics.get('category_accuracy', 0.0))}</span>
  <span><strong>FAQ Accuracy:</strong> {self._pct(metrics.get('faq_accuracy', 0.0))}</span>
</div>
<h2>By Category</h2>
{by_cat_table}
<h2>Failures ({len(metrics.get('failures', []))})</h2>
{failure_table}
</body>
</html>
"""


__all__ = ["AccuracyBenchmark", "DEFAULT_CATEGORY_ALIASES"]


def _iter_testset_items(testset: dict[str, Any]) -> Iterable[dict[str, Any]]:  # pragma: no cover
    return testset.get("items", [])
