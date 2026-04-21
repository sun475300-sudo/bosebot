"""TF-IDF 기반 유사도 매칭 모듈.

외부 라이브러리 없이 순수 Python으로 구현한 TF-IDF 유사도 매칭.
FAQ 질문·키워드와 사용자 질문 간의 유사도를 계산하여 최적 매칭을 반환한다.
"""

import math
from collections import Counter


class TFIDFMatcher:
    """TF-IDF 기반 FAQ 유사도 매칭 클래스."""

    def __init__(self, faq_items: list[dict]):
        """FAQ 데이터로 TF-IDF 벡터를 사전 계산한다.

        Args:
            faq_items: FAQ 항목 리스트. 각 항목에 question, keywords, category 필드 필요.
        """
        self.faq_items = faq_items
        self.documents: list[list[str]] = []
        self.idf: dict[str, float] = {}
        self.tfidf_vectors: list[dict[str, float]] = []

        self._build_documents()
        self._compute_tfidf()

    # 한국어 조사/어미 목록 (길이 내림차순으로 정렬하여 긴 것부터 시도)
    _KO_PARTICLES = sorted([
        "으로부터", "에서부터", "로부터",
        "에서", "이란", "이고", "이며", "이나", "으로", "이라",
        "에게", "한테", "부터", "까지",
        "이는", "하는", "하면", "하여", "되는",
        "에는", "에도", "로는",
        "을는", "이를",
        "은", "는", "이", "가", "을", "를",
        "에", "의", "와", "과", "도", "로", "만",
    ], key=len, reverse=True)

    def _strip_particle(self, token: str) -> str:
        """한국어 조사/어미를 토큰 끝에서 제거한다.

        영문자로만 이루어진 토큰의 경우 한국어 조사가 붙어있을 수 있으므로
        (예: 'carnet이', 'uni-pass에서') 제거를 시도한다.

        Args:
            token: 처리할 토큰.

        Returns:
            조사가 제거된 토큰. 제거 후 길이가 1 이하이면 원본 반환.
        """
        for particle in self._KO_PARTICLES:
            if token.endswith(particle):
                stripped = token[: -len(particle)]
                # 최소 2글자 이상인 경우에만 적용
                if len(stripped) >= 2:
                    return stripped
        return token

    def _tokenize(self, text: str) -> list[str]:
        """한국어 공백 기반 토크나이즈 (조사 처리 포함).

        Args:
            text: 토크나이즈할 텍스트.

        Returns:
            토큰 리스트.
        """
        tokens = []
        for token in text.strip().lower().split():
            token = token.strip("?.,!·()\"'")
            if not token:
                continue
            # 한국어 조사 제거 시도
            token = self._strip_particle(token)
            if len(token) >= 2:
                tokens.append(token)
        return tokens

    def _build_documents(self) -> None:
        """FAQ 항목에서 문서(토큰 리스트)를 생성한다."""
        for item in self.faq_items:
            question = item.get("question", "")
            keywords = item.get("keywords", [])
            answer = item.get("answer", "")

            # 질문 + 키워드 + 답변 첫 문장을 결합하여 문서 구성
            text_parts = [question]
            text_parts.extend(keywords)
            first_sentence = answer.split(".")[0] if answer else ""
            if first_sentence:
                text_parts.append(first_sentence)

            tokens = self._tokenize(" ".join(text_parts))
            self.documents.append(tokens)

    def _compute_tfidf(self) -> None:
        """TF-IDF 행렬을 계산한다."""
        num_docs = len(self.documents)
        if num_docs == 0:
            return

        # 문서 빈도(DF) 계산
        df: dict[str, int] = {}
        for doc in self.documents:
            unique_tokens = set(doc)
            for token in unique_tokens:
                df[token] = df.get(token, 0) + 1

        # IDF 계산: log((N + 1) / (df + 1)) + 1 (smoothing)
        for token, doc_freq in df.items():
            self.idf[token] = math.log((num_docs + 1) / (doc_freq + 1)) + 1

        # 각 문서의 TF-IDF 벡터 계산
        self.tfidf_vectors = []
        for doc in self.documents:
            tf = Counter(doc)
            doc_len = len(doc) if doc else 1
            vector: dict[str, float] = {}
            for token, count in tf.items():
                tf_val = count / doc_len
                idf_val = self.idf.get(token, 1.0)
                vector[token] = tf_val * idf_val
            self.tfidf_vectors.append(vector)

    def _cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        """두 벡터의 코사인 유사도를 계산한다.

        Args:
            vec1: 첫 번째 TF-IDF 벡터.
            vec2: 두 번째 TF-IDF 벡터.

        Returns:
            코사인 유사도 (0.0 ~ 1.0).
        """
        if not vec1 or not vec2:
            return 0.0

        # 공통 키에 대해 내적 계산
        dot_product = 0.0
        for token in vec1:
            if token in vec2:
                dot_product += vec1[token] * vec2[token]

        if dot_product == 0.0:
            return 0.0

        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def find_best_match(
        self, query: str, category: str | None = None, top_k: int = 3
    ) -> list[dict]:
        """유사도 상위 k개 FAQ 항목을 반환한다.

        Args:
            query: 사용자 질문 문자열.
            category: 카테고리 필터 (None이면 전체 검색).
            top_k: 반환할 최대 항목 수.

        Returns:
            [{"item": FAQ항목, "score": 유사도}] 리스트 (유사도 내림차순).
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 쿼리의 TF-IDF 벡터 계산
        tf = Counter(query_tokens)
        query_len = len(query_tokens)
        query_vector: dict[str, float] = {}
        for token, count in tf.items():
            tf_val = count / query_len
            idf_val = self.idf.get(token, 1.0)
            query_vector[token] = tf_val * idf_val

        # 각 FAQ와 유사도 계산
        results: list[dict] = []
        for i, item in enumerate(self.faq_items):
            if category and item.get("category") != category:
                continue

            score = self._cosine_similarity(query_vector, self.tfidf_vectors[i])
            if score > 0.0:
                results.append({"item": item, "score": round(score, 4)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
