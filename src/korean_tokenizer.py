"""한국어 토크나이저 모듈.

보세전시장 챗봇 전용 한국어 토크나이저.
외부 라이브러리 없이 순수 Python으로 구현하며,
도메인 사전 기반 복합명사 처리와 조사/어미 분리를 지원한다.
"""


class KoreanTokenizer:
    """한국어 토크나이저 클래스."""

    # 도메인 특화 용어 — 분리하지 않고 그대로 보존
    DOMAIN_TERMS: set[str] = {
        "보세전시장",
        "보세구역",
        "보세화물",
        "보세운송",
        "견본품",
        "시식용식품",
        "시식용",
        "반출입",
        "반입신고",
        "반출신고",
        "세관장확인",
        "세관장",
        "세관신고",
        "관세법",
        "관세청",
        "관세사",
        "수입신고",
        "수출신고",
        "통관절차",
        "통관",
        "원산지증명",
        "원산지",
        "전시물품",
        "전시장",
        "전시회",
        "면세",
        "면세범위",
        "과세",
        "과세가격",
        "부가세",
        "특허보세",
        # ── LICENSE 도메인 핵심 복합명사 — 분리 금지 ──
        "특허",
        "특허기간",
        "특허신청",
        "특허장소",
        "특허취소",
        "특허연장",
        "특허신청서",
        "설치특허",
        "운영인",
        "장치기간",
        "재반출",
        "재반입",
        "감면",
        "HS코드",
        "FTA",
    }

    SUFFIXES: list[str] = sorted(
        [
            "에서만", "에서도", "인가요", "하나요", "합니다", "입니다",
            "니까", "부터", "까지", "에서", "으로", "해요", "까요", "나요", "하다",
            "은", "는", "이", "가", "을", "를", "에", "로", "도", "의", "와", "과", "요",
        ],
        key=len,
        reverse=True,
    )

    def __init__(self) -> None:
        self._known_short_terms: set[str] = {"세", "관", "법", "세관", "FTA"}

    def _strip_suffix(self, token: str) -> str:
        if token in self.DOMAIN_TERMS:
            return token
        for suffix in self.SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix):
                candidate = token[: -len(suffix)]
                if len(candidate) >= 1:
                    return candidate
        return token

    def _split_compound(self, token: str) -> list[str]:
        if token in self.DOMAIN_TERMS:
            return [token]
        found: list[tuple[int, int, str]] = []
        for term in self.DOMAIN_TERMS:
            start = token.find(term)
            if start != -1:
                found.append((start, start + len(term), term))
        if not found:
            return [token]
        found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        parts: list[str] = []
        prev_end = 0
        for start, end, term in found:
            if start < prev_end:
                continue
            if start > prev_end:
                remainder = token[prev_end:start]
                if remainder:
                    parts.append(remainder)
            parts.append(term)
            prev_end = end
        if prev_end < len(token):
            remainder = token[prev_end:]
            if remainder:
                parts.append(remainder)
        return parts

    def tokenize(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        raw_tokens = text.strip().lower().split()
        result: list[str] = []
        for raw in raw_tokens:
            cleaned = raw.strip("?.,!() \"'~:;")
            if not cleaned:
                continue
            stripped = self._strip_suffix(cleaned)
            parts = self._split_compound(stripped)
            for part in parts:
                if len(part) >= 2:
                    result.append(part)
                elif part in self._known_short_terms or part in self.DOMAIN_TERMS:
                    result.append(part)
        return result

    def extract_ngrams(self, text: str, n: int = 2) -> list[str]:
        if not text:
            return []
        cleaned = ""
        for ch in text.lower():
            if ch.isalnum() or ("가" <= ch <= "힣"):
                cleaned += ch
        if len(cleaned) < n:
            return [cleaned] if cleaned else []
        return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]
