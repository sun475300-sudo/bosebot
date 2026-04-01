"""장기 대화 컨텍스트 메모리 시스템.

세션 간 컨텍스트를 SQLite에 저장하여 장기 대화 기억을 제공한다.
"""

import json
import os
import sqlite3
import time
from collections import Counter
from typing import Any


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "memory.db")


class ContextMemory:
    """SQLite 기반 장기 컨텍스트 메모리."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS context_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_context_session
                    ON context_entries(session_id);
                CREATE INDEX IF NOT EXISTS idx_context_expires
                    ON context_entries(expires_at);

                CREATE TABLE IF NOT EXISTS session_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_session_id TEXT NOT NULL,
                    new_session_id TEXT NOT NULL,
                    linked_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_links_new
                    ON session_links(new_session_id);
                CREATE INDEX IF NOT EXISTS idx_links_old
                    ON session_links(old_session_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def store_context(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl_hours: float = 168,
    ) -> None:
        """컨텍스트를 저장한다. 기본 TTL은 7일(168시간)."""
        now = time.time()
        expires_at = now + ttl_hours * 3600
        serialized = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO context_entries (session_id, key, value, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, key, serialized, now, expires_at),
            )
            conn.commit()
        finally:
            conn.close()

    def get_context(self, session_id: str, key: str | None = None) -> list[dict]:
        """세션의 컨텍스트를 조회한다. key가 None이면 전체 반환."""
        now = time.time()
        conn = self._get_conn()
        try:
            if key is None:
                rows = conn.execute(
                    "SELECT key, value, created_at, expires_at FROM context_entries "
                    "WHERE session_id = ? AND expires_at > ? ORDER BY created_at DESC",
                    (session_id, now),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, value, created_at, expires_at FROM context_entries "
                    "WHERE session_id = ? AND key = ? AND expires_at > ? ORDER BY created_at DESC",
                    (session_id, key, now),
                ).fetchall()
            return [
                {
                    "key": row["key"],
                    "value": self._try_parse_json(row["value"]),
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_user_profile(self, session_id: str) -> dict:
        """축적된 컨텍스트로부터 사용자 프로필을 구성한다."""
        entries = self.get_context(session_id)
        profile: dict[str, Any] = {
            "session_id": session_id,
            "topics": [],
            "preferences": {},
            "total_interactions": 0,
        }
        topics: list[str] = []
        for entry in entries:
            k = entry["key"]
            v = entry["value"]
            if k == "topic":
                topics.append(v if isinstance(v, str) else str(v))
            elif k == "preference":
                if isinstance(v, dict):
                    profile["preferences"].update(v)
                else:
                    profile["preferences"][str(v)] = True
            profile["total_interactions"] += 1

        # 빈도 기반 상위 토픽
        topic_counts = Counter(topics)
        profile["topics"] = [t for t, _ in topic_counts.most_common(10)]
        return profile

    def get_previous_sessions(self, session_id: str, limit: int = 5) -> list[str]:
        """연결된 이전 세션 ID 목록을 반환한다."""
        conn = self._get_conn()
        try:
            # 직접 연결된 이전 세션
            rows = conn.execute(
                "SELECT DISTINCT old_session_id FROM session_links "
                "WHERE new_session_id = ? ORDER BY linked_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            result = [row["old_session_id"] for row in rows]

            # 역방향도 확인 (이전 세션에서 현재 세션으로 연결된 것)
            if len(result) < limit:
                rows2 = conn.execute(
                    "SELECT DISTINCT new_session_id FROM session_links "
                    "WHERE old_session_id = ? ORDER BY linked_at DESC LIMIT ?",
                    (session_id, limit - len(result)),
                ).fetchall()
                for row in rows2:
                    sid = row["new_session_id"]
                    if sid not in result and sid != session_id:
                        result.append(sid)

            return result[:limit]
        finally:
            conn.close()

    def merge_context(self, old_session_id: str, new_session_id: str) -> int:
        """이전 세션의 유효한 컨텍스트를 새 세션으로 이관한다."""
        now = time.time()
        conn = self._get_conn()
        try:
            # 링크 기록
            conn.execute(
                "INSERT INTO session_links (old_session_id, new_session_id, linked_at) "
                "VALUES (?, ?, ?)",
                (old_session_id, new_session_id, now),
            )

            # 만료되지 않은 항목 복사
            cursor = conn.execute(
                "SELECT key, value, created_at, expires_at FROM context_entries "
                "WHERE session_id = ? AND expires_at > ?",
                (old_session_id, now),
            )
            rows = cursor.fetchall()
            count = 0
            for row in rows:
                conn.execute(
                    "INSERT INTO context_entries (session_id, key, value, created_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (new_session_id, row["key"], row["value"], row["created_at"], row["expires_at"]),
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def forget(self, session_id: str, key: str | None = None) -> int:
        """컨텍스트를 삭제한다. key가 None이면 세션 전체 삭제."""
        conn = self._get_conn()
        try:
            if key is None:
                cursor = conn.execute(
                    "DELETE FROM context_entries WHERE session_id = ?",
                    (session_id,),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM context_entries WHERE session_id = ? AND key = ?",
                    (session_id, key),
                )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def cleanup_expired(self) -> int:
        """만료된 항목을 모두 삭제하고 삭제된 수를 반환한다."""
        now = time.time()
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM context_entries WHERE expires_at <= ?",
                (now,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    @staticmethod
    def _try_parse_json(value: str) -> Any:
        """JSON 파싱을 시도하고 실패하면 원본 문자열을 반환한다."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


class ConversationMemoryManager:
    """대화 기억 관리자. ContextMemory 위에 고수준 기능을 제공한다."""

    def __init__(self, context_memory: ContextMemory | None = None):
        self.memory = context_memory or ContextMemory()

    def remember_topic(self, session_id: str, topic: str, category: str) -> None:
        """대화 토픽을 기억한다."""
        self.memory.store_context(session_id, "topic", topic)
        self.memory.store_context(session_id, "category", category)

    def get_conversation_resume(self, session_id: str) -> str | None:
        """이전 대화 요약을 반환한다. 이전 기록이 없으면 None."""
        topics = self.memory.get_context(session_id, key="topic")
        if not topics:
            return None
        # 가장 최근 토픽 (get_context는 created_at DESC)
        recent_topic = topics[0]["value"]
        return f"지난번에 '{recent_topic}'에 대해 문의하셨습니다."

    def is_returning_user(self, session_id: str) -> bool:
        """이전 세션 기록이 있는 재방문 사용자인지 확인한다."""
        previous = self.memory.get_previous_sessions(session_id)
        if previous:
            return True
        # 현재 세션에 기존 컨텍스트가 있는지도 확인
        entries = self.memory.get_context(session_id)
        return len(entries) > 0
