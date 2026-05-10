"""한국어 토크나이저 서비스 — src/korean_tokenizer.py 비동기 래퍼."""

import asyncio


class TokenizerService:
    async def tokenize(self, text: str) -> list[str]:
        return await asyncio.to_thread(self._tokenize_sync, text)

    @staticmethod
    def _tokenize_sync(text: str) -> list[str]:
        from src.korean_tokenizer import tokenize
        return tokenize(text)
