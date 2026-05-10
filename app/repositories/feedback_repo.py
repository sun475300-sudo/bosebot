"""사용자 피드백 비동기 repository.

feedback 스키마:
  id INTEGER PK AUTOINCREMENT
  query_id TEXT NOT NULL
  timestamp TEXT        (YYYY-MM-DD HH:MM:SS)
  rating TEXT NOT NULL  (helpful | unhelpful)
  comment TEXT DEFAULT ""
"""

from datetime import datetime
from typing import Any
from app.repositories.base import AsyncDBPool

import structlog

log = structlog.get_logger(__name__)


class FeedbackRepository:
    VALID_RATINGS = frozenset({"helpful", "unhelpful"})

    def __init__(self, pool: AsyncDBPool) -> None:
        self._pool = pool

    async def init_table(self) -> None:
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                rating TEXT NOT NULL,
                comment TEXT DEFAULT ""
            )
        """)
        await self._pool.commit()

    async def save_feedback(self, query_id: str, rating: str, comment: str = "") -> int:
        if rating not in self.VALID_RATINGS:
            raise ValueError(f"rating은 {self.VALID_RATINGS} 중 하나여야 합니다: {rating!r}")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = await self._pool.execute(
            """INSERT INTO feedback (query_id, timestamp, rating, comment)
               VALUES (?, ?, ?, ?)""",
            (query_id, timestamp, rating, comment or ""),
        )
        await self._pool.commit()
        return cur.lastrowid or 0

    async def get_stats(self) -> dict[str, Any]:
        total_row = await self._pool.fetchone("SELECT COUNT(*) AS cnt FROM feedback")
        total = total_row["cnt"] if total_row else 0
        helpful_row = await self._pool.fetchone(
            "SELECT COUNT(*) AS cnt FROM feedback WHERE rating = ?", ("helpful",)
        )
        helpful = helpful_row["cnt"] if helpful_row else 0
        return {
            "total_feedback": total,
            "helpful_count": helpful,
            "unhelpful_count": total - helpful,
            "satisfaction_rate": helpful / total if total else 0.0,
        }
