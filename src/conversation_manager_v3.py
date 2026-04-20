"""Advanced multi-turn conversation manager with topic tracking (v3).

This module implements ConversationManagerV3 and TopicTracker. Both are
self-contained and rely only on stdlib + the project's classifier.

Design goals:
- Persist turns to SQLite (data/conversation_v3.db by default).
- Provide rich context retrieval (last N turns with category/entities).
- Detect topic shift by comparing the new query's top category with the
  current conversation's dominant category.
- Generate a follow-up question based on the most recent category/entities
  using lightweight templates (no external LLM required).
- Track the sequence of categories per session and expose a coherence check.
- Thread-safe via ``threading.Lock``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections import Counter
from typing import Any, Iterable

from src.classifier import classify_query


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "conversation_v3.db")


# Lightweight follow-up templates keyed by category. ``{entity}`` will be
# replaced with the first available entity if provided.
_FOLLOWUP_TEMPLATES: dict[str, list[str]] = {
    "GENERAL": [
        "보세전시장 제도에 대해 더 궁금한 점이 있으신가요?",
        "{entity}에 대해 더 자세히 알려드릴까요?",
    ],
    "LICENSE": [
        "특허 신청 절차에 대해서도 안내해 드릴까요?",
        "{entity} 관련 특허 요건을 더 확인하시겠어요?",
    ],
    "IMPORT_EXPORT": [
        "반입/반출 서류 준비에 대해서도 안내해 드릴까요?",
        "{entity}의 반출 방법에 대해 더 알아보시겠어요?",
    ],
    "EXHIBITION": [
        "전시 기간이나 장치 요건도 확인해 보시겠어요?",
        "{entity} 전시 운영에 대해 더 궁금한 점이 있으신가요?",
    ],
    "SALES": [
        "현장 판매 시 관세 납부 절차도 안내해 드릴까요?",
        "{entity} 판매 관련 추가 질문이 있으신가요?",
    ],
    "SAMPLE": [
        "견본품 관세 면제 조건에 대해서도 알려드릴까요?",
        "{entity} 견본 처리 방법을 더 확인하시겠어요?",
    ],
    "FOOD_TASTING": [
        "시식 식품의 위생 요건도 확인해 드릴까요?",
        "{entity} 시식 운영 방법을 안내해 드릴까요?",
    ],
    "DOCUMENTS": [
        "서류 제출 방법에 대해서도 도와드릴까요?",
        "{entity} 관련 서식을 더 확인하시겠어요?",
    ],
    "PENALTIES": [
        "위반 시 구제 절차에 대해서도 안내해 드릴까요?",
        "{entity} 관련 제재 기준을 더 알아보시겠어요?",
    ],
    "CONTACT": [
        "담당 부서 연락처 외에 다른 안내가 필요하신가요?",
        "{entity} 관련 문의 창구를 안내해 드릴까요?",
    ],
}

_DEFAULT_FOLLOWUP = "추가로 궁금하신 점이 있으신가요?"


class TopicTracker:
    """Tracks per-session category sequences to detect coherence/shift."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._paths: dict[str, list[str]] = {}

    def track(self, session_id: str, category: str) -> None:
        """Append ``category`` to the session's topic path."""
        if not session_id or not category:
            return
        with self._lock:
            self._paths.setdefault(session_id, []).append(category)

    def get_topic_path(self, session_id: str) -> list[str]:
        """Return the full sequence of categories for the session."""
        with self._lock:
            return list(self._paths.get(session_id, []))

    def is_coherent(self, session_id: str, window: int = 5) -> bool:
        """Return True if the last ``window`` categories are dominated by one.

        A session is considered coherent if at least half of the recent
        categories are the same. An empty or single-entry path is coherent
        by definition.
        """
        with self._lock:
            path = list(self._paths.get(session_id, []))
        if len(path) <= 1:
            return True
        recent = path[-window:]
        counts = Counter(recent)
        top_count = counts.most_common(1)[0][1]
        return top_count * 2 >= len(recent)

    def reset(self, session_id: str) -> None:
        """Drop the session's tracked path."""
        with self._lock:
            self._paths.pop(session_id, None)


class ConversationManagerV3:
    """Multi-turn conversation manager backed by SQLite."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        topic_tracker: TopicTracker | None = None,
    ) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.topic_tracker = topic_tracker or TopicTracker()
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        turn_index INTEGER NOT NULL,
                        query TEXT NOT NULL,
                        response TEXT NOT NULL,
                        category TEXT NOT NULL,
                        entities TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_turns_session
                        ON conversation_turns(session_id);
                    CREATE INDEX IF NOT EXISTS idx_turns_created
                        ON conversation_turns(created_at);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_turn(
        self,
        session_id: str,
        query: str,
        response: str,
        category: str | None = None,
        entities: Iterable[str] | dict[str, Any] | None = None,
    ) -> int:
        """Record a new conversation turn.

        Returns the stored turn's row id.
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        cat = (category or "").strip()
        if not cat:
            cats = classify_query(query or "")
            cat = cats[0] if cats else "GENERAL"
        ents = entities if entities is not None else []
        entities_json = json.dumps(ents, ensure_ascii=False)
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM conversation_turns WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                turn_index = int(row["c"]) if row else 0
                cursor = conn.execute(
                    "INSERT INTO conversation_turns "
                    "(session_id, turn_index, query, response, category, entities, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        turn_index,
                        query or "",
                        response or "",
                        cat,
                        entities_json,
                        now,
                    ),
                )
                conn.commit()
                row_id = cursor.lastrowid
            finally:
                conn.close()

        # Track topic outside the DB lock
        self.topic_tracker.track(session_id, cat)
        return int(row_id)

    def get_context(self, session_id: str, n: int = 10) -> list[dict]:
        """Return the last ``n`` turns in chronological order (oldest→newest).

        Each item contains: turn_index, query, response, category, entities,
        created_at.
        """
        if n <= 0:
            return []
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT turn_index, query, response, category, entities, created_at "
                    "FROM conversation_turns WHERE session_id = ? "
                    "ORDER BY turn_index DESC LIMIT ?",
                    (session_id, n),
                ).fetchall()
            finally:
                conn.close()
        items: list[dict] = []
        for row in rows:
            try:
                entities = json.loads(row["entities"])
            except (TypeError, ValueError, json.JSONDecodeError):
                entities = []
            items.append(
                {
                    "turn_index": row["turn_index"],
                    "query": row["query"],
                    "response": row["response"],
                    "category": row["category"],
                    "entities": entities,
                    "created_at": row["created_at"],
                }
            )
        items.reverse()
        return items

    def _dominant_category(self, session_id: str) -> str | None:
        """Return the most frequent category in recent history, or None."""
        context = self.get_context(session_id, n=10)
        if not context:
            return None
        counts = Counter(turn["category"] for turn in context if turn.get("category"))
        if not counts:
            return None
        return counts.most_common(1)[0][0]

    def detect_topic_shift(self, session_id: str, new_query: str) -> bool:
        """Return True if ``new_query``'s category differs from the dominant one.

        If there is no prior history the answer is False (nothing to shift
        away from).
        """
        dominant = self._dominant_category(session_id)
        if dominant is None:
            return False
        categories = classify_query(new_query or "")
        new_cat = categories[0] if categories else "GENERAL"
        return new_cat != dominant

    def generate_followup_question(self, session_id: str) -> str:
        """Generate a follow-up question based on the latest turn."""
        context = self.get_context(session_id, n=1)
        if not context:
            return _DEFAULT_FOLLOWUP
        last = context[-1]
        category = last.get("category") or "GENERAL"
        entities = last.get("entities") or []

        entity_str: str | None = None
        if isinstance(entities, list) and entities:
            first = entities[0]
            if isinstance(first, str) and first.strip():
                entity_str = first.strip()
            elif isinstance(first, dict):
                for key in ("text", "name", "value"):
                    val = first.get(key)
                    if isinstance(val, str) and val.strip():
                        entity_str = val.strip()
                        break
        elif isinstance(entities, dict) and entities:
            for val in entities.values():
                if isinstance(val, str) and val.strip():
                    entity_str = val.strip()
                    break

        templates = _FOLLOWUP_TEMPLATES.get(category) or _FOLLOWUP_TEMPLATES["GENERAL"]
        if entity_str:
            for tmpl in templates:
                if "{entity}" in tmpl:
                    return tmpl.format(entity=entity_str)
        for tmpl in templates:
            if "{entity}" not in tmpl:
                return tmpl
        # Fallback: strip placeholder
        return templates[0].replace("{entity}", "해당 사항")

    def get_conversation_summary(self, session_id: str) -> dict:
        """Return a lightweight summary of the conversation so far."""
        context = self.get_context(session_id, n=1000)
        if not context:
            return {
                "session_id": session_id,
                "turn_count": 0,
                "categories": [],
                "dominant_category": None,
                "topic_path": self.topic_tracker.get_topic_path(session_id),
                "first_query": None,
                "last_query": None,
                "duration_seconds": 0.0,
            }
        cat_counter = Counter(turn["category"] for turn in context if turn.get("category"))
        dominant = cat_counter.most_common(1)[0][0] if cat_counter else None
        duration = max(0.0, context[-1]["created_at"] - context[0]["created_at"])
        return {
            "session_id": session_id,
            "turn_count": len(context),
            "categories": [cat for cat, _ in cat_counter.most_common()],
            "dominant_category": dominant,
            "topic_path": self.topic_tracker.get_topic_path(session_id),
            "first_query": context[0]["query"],
            "last_query": context[-1]["query"],
            "duration_seconds": round(duration, 3),
        }

    def reset_context(self, session_id: str) -> int:
        """Delete all turns for the session and reset the topic path.

        Returns the number of deleted rows.
        """
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM conversation_turns WHERE session_id = ?",
                    (session_id,),
                )
                conn.commit()
                deleted = cursor.rowcount
            finally:
                conn.close()
        self.topic_tracker.reset(session_id)
        return int(deleted)
