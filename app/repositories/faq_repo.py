"""FAQ 데이터 비동기 repository.

data/faq.json 구조:
  faq_version: str
  last_updated: str (YYYY-MM-DD)
  items: list of FAQ items
    id: str
    category: str
    question: str
    answer: str
    legal_basis: list[str]
    notes: str
    keywords: list[str]
"""

import asyncio
import hashlib
import json
from typing import Any


class FAQRepository:
    """FAQ 항목을 data/faq.json에서 비동기적으로 읽고 캐싱한다."""

    def __init__(self, faq_path: str = "data/faq.json") -> None:
        self._path = faq_path
        self._items: list[dict[str, Any]] = []
        self._version: str = ""
        self._corpus_hash: str = ""
        self._by_id: dict[str, dict[str, Any]] = {}

    async def load(self) -> None:
        """FAQ 파일을 비동기로 읽고 인덱스를 빌드한다."""
        raw = await asyncio.to_thread(self._read_file)
        data: dict[str, Any] = json.loads(raw)
        self._items = data.get("items", [])
        self._version = data.get("faq_version", "unknown")
        self._corpus_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
        self._by_id = {item["id"]: item for item in self._items}

    def _read_file(self) -> str:
        with open(self._path, encoding="utf-8") as f:
            return f.read()

    async def reload(self) -> None:
        """FAQ 파일 변경 시 런타임 리로드."""
        await self.load()

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._items)

    def get_by_id(self, faq_id: str) -> dict[str, Any] | None:
        return self._by_id.get(faq_id)

    def get_by_category(self, category: str) -> list[dict[str, Any]]:
        return [item for item in self._items if item.get("category") == category]

    @property
    def version(self) -> str:
        return self._version

    @property
    def corpus_hash(self) -> str:
        """FAQ 코퍼스 버전 해시 — 캐시 무효화에 사용."""
        return self._corpus_hash

    @property
    def count(self) -> int:
        return len(self._items)
