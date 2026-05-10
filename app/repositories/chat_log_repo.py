"""챗봇 대화 로그 비동기 repository.

chat_logs 스키마:
  id INTEGER PK AUTOINCREMENT
  timestamp TEXT        (YYYY-MM-DD HH:MM:SS)
  query TEXT NOT NULL
  category TEXT
  faq_id TEXT
  is_escalation INTEGER DEFAULT 0
  response_preview TEXT
"""

from datetime import datetime
from typing import Any
from app.repositories.base import AsyncDBPool

import structlog

log = structlog.get_logger(__name__)


class ChatLogRepository:
    def __init__(self, pool: AsyncDBPool) -> None:
        self._pool = pool

    async def init_table(self) -> None:
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                query TEXT NOT NULL,
                category TEXT,
                faq_id TEXT,
                is_escalation INTEGER NOT NULL DEFAULT 0,
                response_preview TEXT
            )
        """)
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_logs_ts ON chat_logs (timestamp)"
        )
        await self._pool.commit()

    async def log_query(
        self,
        query: str,
        category: str | None = None,
        faq_id: str | None = None,
        is_escalation: bool = False,
        response_preview: str | None = None,
    ) -> int:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        preview = response_preview[:200] if response_preview else None
        cur = await self._pool.execute(
            """INSERT INTO chat_logs
               (timestamp, query, category, faq_id, is_escalation, response_preview)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (timestamp, query, category, faq_id, 1 if is_escalation else 0, preview),
        )
        await self._pool.commit()
        return cur.lastrowid or 0

    async def get_stats(self) -> dict[str, Any]:
        total_row = await self._pool.fetchone("SELECT COUNT(*) AS cnt FROM chat_logs")
        total = total_row["cnt"] if total_row else 0
        rows = await self._pool.fetchall(
            "SELECT category, COUNT(*) AS cnt FROM chat_logs GROUP BY category"
        )
        category_distribution = {(r["category"] or "UNKNOWN"): r["cnt"] for r in rows}
        esc_row = await self._pool.fetchone(
            "SELECT COUNT(*) AS cnt FROM chat_logs WHERE is_escalation = 1"
        )
        escalation_count = esc_row["cnt"] if esc_row else 0
        unmatched_row = await self._pool.fetchone(
            "SELECT COUNT(*) AS cnt FROM chat_logs WHERE faq_id IS NULL AND is_escalation = 0"
        )
        unmatched_count = unmatched_row["cnt"] if unmatched_row else 0
        return {
            "total_queries": total,
            "category_distribution": category_distribution,
            "escalation_rate": escalation_count / total if total else 0.0,
            "unmatched_rate": unmatched_count / total if total else 0.0,
        }

    async def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self._pool.fetchall(
            "SELECT * FROM chat_logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    async def get_unmatched_queries(self, limit: int = 200) -> list[str]:
        rows = await self._pool.fetchall(
            """SELECT query FROM chat_logs
               WHERE faq_id IS NULL AND is_escalation = 0
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return [r["query"] for r in rows]
