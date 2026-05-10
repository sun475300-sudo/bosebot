"""NLP 전처리 서비스 — 맞춤법 교정 + 동의어 확장 + 정규화.

기존 구현 래핑 (재작성 없음):
  src/spell_corrector.py:correct_query -> (corrected: str, corrections: list)
  src/synonym_resolver.py:expand_query -> str
  src/utils.py:normalize_query -> str
"""

import asyncio
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PreprocessedQuery:
    original: str
    normalized: str
    spell_corrected: str
    expanded: str


class Preprocessor:
    """비동기 전처리 파이프라인."""

    async def process(self, query: str) -> PreprocessedQuery:
        normalized, spell_corrected, expanded = await asyncio.to_thread(
            self._run_pipeline, query
        )
        return PreprocessedQuery(
            original=query,
            normalized=normalized,
            spell_corrected=spell_corrected,
            expanded=expanded,
        )

    @staticmethod
    def _run_pipeline(query: str) -> tuple[str, str, str]:
        from src.utils import normalize_query
        from src.spell_corrector import correct_query
        from src.synonym_resolver import expand_query
        normalized = normalize_query(query)
        # correct_query returns (corrected_str, corrections_list)
        spell_result = correct_query(normalized)
        spell_corrected = spell_result[0] if isinstance(spell_result, tuple) else spell_result
        expanded = expand_query(spell_corrected)
        # expand_query may also return a tuple in some versions
        if isinstance(expanded, tuple):
            expanded = expanded[0]
        return normalized, spell_corrected, expanded
