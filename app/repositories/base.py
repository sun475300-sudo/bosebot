"""aiosqlite 기반 비동기 Repository 기반 클래스."""

import aiosqlite
import os
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class AsyncDBPool:
    """단일 aiosqlite 연결 (단일 writer + WAL 패턴)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("DB not connected — call connect() first")
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        return await self.conn.execute(sql, params)

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchall()

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def commit(self) -> None:
        await self.conn.commit()
