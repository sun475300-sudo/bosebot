"""의도 분류 서비스 — src/classifier.py 비동기 래퍼."""

import asyncio
from app.models.intent import IntentClassification
from app.models.faq import FAQCategory
from app.services.nlp.preprocessor import PreprocessedQuery


class ClassifierService:
    async def classify(self, pq: PreprocessedQuery) -> IntentClassification:
        result = await asyncio.to_thread(self._classify_sync, pq.expanded)
        return result

    @staticmethod
    def _classify_sync(query: str) -> IntentClassification:
        from src.classifier import classify_query

        categories = classify_query(query)
        primary = categories[0] if categories else "UNKNOWN"
        try:
            primary_cat = FAQCategory(primary)
        except ValueError:
            primary_cat = FAQCategory.UNKNOWN

        mapped = []
        for c in categories:
            try:
                mapped.append(FAQCategory(c))
            except ValueError:
                pass

        return IntentClassification(
            primary_category=primary_cat,
            categories=mapped,
            confidence=0.8 if categories else 0.0,
            intent=primary,
        )
