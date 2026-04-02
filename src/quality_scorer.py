"""Response quality scoring system for chatbot Q&A pairs.

Evaluates response quality across multiple dimensions: relevance,
completeness, specificity, readability, and legal accuracy.
"""

import re
import statistics
from datetime import datetime, timedelta


# Expected sections by category for completeness scoring
EXPECTED_SECTIONS = ["conclusion", "explanation", "legal_basis", "disclaimer"]

# Legal reference patterns per category
CATEGORY_LEGAL_REFS = {
    "입장절차": ["관세법", "보세화물", "제156조", "제157조", "제174조"],
    "반출입": ["관세법", "보세운송", "제213조", "제214조", "제215조"],
    "세금": ["관세법", "부가가치세", "제241조", "제16조", "관세율"],
    "보험": ["보험업법", "적하보험", "보상"],
    "전시품관리": ["관세법", "보세화물", "제157조", "장치기간"],
    "통관": ["관세법", "수입신고", "제241조", "제248조", "통관"],
    "보세구역": ["관세법", "보세구역", "제154조", "제156조", "특허"],
    "위반사항": ["관세법", "벌칙", "제269조", "제270조", "과태료"],
    "기타": [],
}

# Section indicator keywords (Korean)
SECTION_INDICATORS = {
    "conclusion": ["결론", "요약", "따라서", "그러므로", "결과적으로", "정리하면"],
    "explanation": ["설명", "내용", "이란", "것은", "의미", "대해", "관련하여"],
    "legal_basis": ["법적", "근거", "관세법", "조항", "제", "조", "항", "규정"],
    "disclaimer": ["참고", "유의", "주의", "확인", "문의", "상담"],
}


class ResponseQualityScorer:
    """Scores chatbot responses on a 0-100 scale with detailed breakdown."""

    def __init__(self, chat_logger=None):
        """Initialize scorer.

        Args:
            chat_logger: Optional ChatLogger instance for historical data.
        """
        self.chat_logger = chat_logger
        self._scored_history: list[dict] = []

    def score_response(self, query: str, answer: str, category: str = "") -> dict:
        """Score a single Q&A pair.

        Args:
            query: The user question.
            answer: The chatbot response.
            category: FAQ category for context-aware scoring.

        Returns:
            Dict with total score (0-100) and breakdown by dimension.
        """
        breakdown = {
            "relevance": self._score_relevance(query, answer),
            "completeness": self._score_completeness(answer),
            "specificity": self._score_specificity(answer),
            "readability": self._score_readability(answer),
            "legal_accuracy": self._score_legal_accuracy(answer, category),
        }
        total = sum(breakdown.values())

        result = {
            "total_score": total,
            "breakdown": breakdown,
            "query": query,
            "answer": answer,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        }

        self._scored_history.append(result)
        return result

    def score_batch(self, qa_pairs: list[dict]) -> list[dict]:
        """Score multiple Q&A pairs.

        Args:
            qa_pairs: List of dicts with 'query', 'answer', and optionally 'category'.

        Returns:
            List of score results.
        """
        results = []
        for pair in qa_pairs:
            query = pair.get("query", "")
            answer = pair.get("answer", "")
            category = pair.get("category", "")
            results.append(self.score_response(query, answer, category))
        return results

    def get_low_quality_responses(self, threshold: int = 60) -> list[dict]:
        """Find responses scoring below the threshold.

        Args:
            threshold: Minimum acceptable quality score (default 60).

        Returns:
            List of score results below the threshold, sorted ascending.
        """
        low = [
            entry for entry in self._scored_history
            if entry["total_score"] < threshold
        ]
        return sorted(low, key=lambda x: x["total_score"])

    def get_quality_trend(self, days: int = 30) -> list[dict]:
        """Get average quality scores per day over a time period.

        Args:
            days: Number of days to look back.

        Returns:
            List of {date, avg_score, count} dicts.
        """
        cutoff = datetime.now() - timedelta(days=days)
        daily: dict[str, list[int]] = {}

        for entry in self._scored_history:
            ts = entry.get("timestamp", "")
            try:
                entry_date = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                continue

            if entry_date < cutoff:
                continue

            date_str = entry_date.strftime("%Y-%m-%d")
            daily.setdefault(date_str, []).append(entry["total_score"])

        trend = []
        for date_str in sorted(daily.keys()):
            scores = daily[date_str]
            trend.append({
                "date": date_str,
                "avg_score": round(statistics.mean(scores), 1),
                "count": len(scores),
            })
        return trend

    def suggest_improvements(
        self, query: str, answer: str, score_breakdown: dict
    ) -> list[str]:
        """Suggest how to improve a response based on score breakdown.

        Args:
            query: The original query.
            answer: The response text.
            score_breakdown: The breakdown dict from score_response.

        Returns:
            List of improvement suggestion strings.
        """
        suggestions: list[str] = []

        relevance = score_breakdown.get("relevance", 0)
        completeness = score_breakdown.get("completeness", 0)
        specificity = score_breakdown.get("specificity", 0)
        readability = score_breakdown.get("readability", 0)
        legal_accuracy = score_breakdown.get("legal_accuracy", 0)

        if relevance < 15:
            suggestions.append(
                "Increase keyword overlap: include more terms from the user query "
                "in the response to improve relevance."
            )

        if completeness < 13:
            missing = self._find_missing_sections(answer)
            if missing:
                suggestions.append(
                    f"Add missing sections: {', '.join(missing)}. "
                    "A complete response should include a conclusion, explanation, "
                    "legal basis, and disclaimer."
                )

        if specificity < 10:
            suggestions.append(
                "Add specific facts: include article numbers, dates, amounts, "
                "or concrete references to improve specificity."
            )

        if readability < 8:
            answer_len = len(answer)
            if answer_len < 50:
                suggestions.append(
                    "Response is too short. Provide a more detailed explanation."
                )
            elif answer_len > 1000:
                suggestions.append(
                    "Response is very long. Consider breaking it into shorter, "
                    "clearer paragraphs."
                )
            else:
                suggestions.append(
                    "Improve sentence structure: use shorter sentences and "
                    "clearer paragraph breaks."
                )

        if legal_accuracy < 5:
            suggestions.append(
                "Include relevant legal references (e.g., specific articles of "
                "관세법) to improve legal accuracy."
            )

        if not suggestions:
            suggestions.append("Response quality is good. No major improvements needed.")

        return suggestions

    # ---- Private scoring methods ----

    def _score_relevance(self, query: str, answer: str) -> int:
        """Score keyword overlap between query and answer (0-30)."""
        if not query or not answer:
            return 0

        query_words = set(self._tokenize(query))
        answer_words = set(self._tokenize(answer))

        if not query_words:
            return 0

        overlap = len(query_words & answer_words)
        ratio = overlap / len(query_words)

        # Scale to 0-30
        return min(30, round(ratio * 30))

    def _score_completeness(self, answer: str) -> int:
        """Score whether answer has expected sections (0-25)."""
        if not answer:
            return 0

        found = 0
        for section, indicators in SECTION_INDICATORS.items():
            for indicator in indicators:
                if indicator in answer:
                    found += 1
                    break

        total_sections = len(EXPECTED_SECTIONS)
        ratio = found / total_sections
        return min(25, round(ratio * 25))

    def _score_specificity(self, answer: str) -> int:
        """Score presence of specific facts, numbers, article references (0-20)."""
        if not answer:
            return 0

        score = 0

        # Check for numbers / amounts
        if re.search(r"\d+", answer):
            score += 5

        # Check for article references (제XX조)
        if re.search(r"제\d+조", answer):
            score += 5

        # Check for specific legal terms
        legal_terms = ["관세법", "시행령", "시행규칙", "고시", "통첩"]
        for term in legal_terms:
            if term in answer:
                score += 2

        # Check for specific proper nouns / institutions
        institutions = ["관세청", "세관", "한국무역협회", "국세청"]
        for inst in institutions:
            if inst in answer:
                score += 1

        return min(20, score)

    def _score_readability(self, answer: str) -> int:
        """Score appropriate length and sentence structure (0-15)."""
        if not answer:
            return 0

        score = 0
        answer_len = len(answer)

        # Length scoring: too short or too long is penalized
        if 50 <= answer_len <= 800:
            score += 7
        elif 30 <= answer_len < 50 or 800 < answer_len <= 1200:
            score += 4
        elif answer_len > 1200:
            score += 2
        else:
            score += 1

        # Sentence structure: check for sentence-ending punctuation
        sentences = re.split(r"[.!?。]\s*", answer)
        sentences = [s for s in sentences if s.strip()]
        num_sentences = len(sentences)

        if 2 <= num_sentences <= 10:
            score += 5
        elif num_sentences == 1:
            score += 2
        elif num_sentences > 10:
            score += 3

        # Paragraph breaks
        if "\n" in answer:
            score += 3
        else:
            score += 1

        return min(15, score)

    def _score_legal_accuracy(self, answer: str, category: str) -> int:
        """Score whether answer cites correct legal references for category (0-10)."""
        if not answer or not category:
            return 0

        expected_refs = CATEGORY_LEGAL_REFS.get(category, [])
        if not expected_refs:
            # No specific legal refs expected; give partial credit if any legal term present
            if re.search(r"제\d+조|관세법|법률|규정", answer):
                return 5
            return 0

        found = 0
        for ref in expected_refs:
            if ref in answer:
                found += 1

        if not expected_refs:
            return 0

        ratio = found / len(expected_refs)
        return min(10, round(ratio * 10))

    def _find_missing_sections(self, answer: str) -> list[str]:
        """Return list of section names not found in the answer."""
        missing = []
        for section, indicators in SECTION_INDICATORS.items():
            found = any(indicator in answer for indicator in indicators)
            if not found:
                missing.append(section)
        return missing

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace + punctuation tokenizer."""
        # Remove punctuation and split on whitespace
        cleaned = re.sub(r"[^\w\s]", " ", text)
        tokens = [t.strip().lower() for t in cleaned.split() if len(t.strip()) >= 2]
        return tokens


class QualityReport:
    """Generates comprehensive quality reports."""

    def __init__(self, scorer: ResponseQualityScorer):
        """Initialize with a scorer instance.

        Args:
            scorer: ResponseQualityScorer with scored history.
        """
        self.scorer = scorer

    def generate(self, days: int = 30) -> dict:
        """Generate a comprehensive quality report.

        Args:
            days: Number of days to include.

        Returns:
            Report dict with summary, trend, category breakdown, and low quality items.
        """
        cutoff = datetime.now() - timedelta(days=days)
        history = self.scorer._scored_history

        # Filter to time window
        entries = []
        for entry in history:
            try:
                ts = datetime.fromisoformat(entry.get("timestamp", ""))
                if ts >= cutoff:
                    entries.append(entry)
            except (ValueError, TypeError):
                entries.append(entry)  # include entries without valid timestamps

        if not entries:
            return {
                "period_days": days,
                "total_scored": 0,
                "avg_score": 0,
                "score_distribution": {},
                "category_quality": {},
                "trend": [],
                "low_quality_count": 0,
                "dimension_averages": {},
            }

        scores = [e["total_score"] for e in entries]

        # Score distribution buckets
        distribution = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for s in scores:
            if s <= 20:
                distribution["0-20"] += 1
            elif s <= 40:
                distribution["21-40"] += 1
            elif s <= 60:
                distribution["41-60"] += 1
            elif s <= 80:
                distribution["61-80"] += 1
            else:
                distribution["81-100"] += 1

        # Dimension averages
        dimensions = ["relevance", "completeness", "specificity", "readability", "legal_accuracy"]
        dim_avgs = {}
        for dim in dimensions:
            vals = [e["breakdown"].get(dim, 0) for e in entries]
            dim_avgs[dim] = round(statistics.mean(vals), 1) if vals else 0

        return {
            "period_days": days,
            "total_scored": len(entries),
            "avg_score": round(statistics.mean(scores), 1),
            "min_score": min(scores),
            "max_score": max(scores),
            "score_distribution": distribution,
            "category_quality": self.get_category_quality(entries),
            "trend": self.scorer.get_quality_trend(days),
            "low_quality_count": sum(1 for s in scores if s < 60),
            "dimension_averages": dim_avgs,
        }

    def get_category_quality(self, entries: list[dict] | None = None) -> dict:
        """Get average quality score per category.

        Args:
            entries: Optional list of score entries. Uses full history if None.

        Returns:
            Dict mapping category to {avg_score, count}.
        """
        if entries is None:
            entries = self.scorer._scored_history

        by_category: dict[str, list[int]] = {}
        for entry in entries:
            cat = entry.get("category", "unknown") or "unknown"
            by_category.setdefault(cat, []).append(entry["total_score"])

        result = {}
        for cat, scores in sorted(by_category.items()):
            result[cat] = {
                "avg_score": round(statistics.mean(scores), 1),
                "count": len(scores),
            }
        return result
