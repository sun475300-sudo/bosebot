"""TF-IDF 기반 유사도 매칭 모듈.

순수 Python 구현. 외부 라이브러리 없이 FAQ 질문과 사용자 질문의 유사도를 계산한다.
"""

import math
from collections import Counter


class TFIDFMatcher:
    """TF-IDF 기반 FAQ 유사도 매칭 클래스."""

    def __init__(self, faq_items: list[dict]):
        self.faq_items = faq_items
        self.documents = []
        self.vocab = set()
        self.idf = {}
        self.tfidf_vectors = []
        self._build_index()

    def _tokenize(self, text: str) -> list[str]:
        """텍스트를 토큰으로 분리한다 (한국어 공백 기반 + 조사 제거)."""
        tokens = text.lower().replace("?", "").replace(".", "").replace(",", "").split()
        # 1글자 토큰 제거 (조사 등)
        return [t for t in tokens if len(t) > 1]

    def _build_index(self):
        """FAQ 문서의 TF-IDF 인덱스를 구축한다."""
        # 문서 토큰화 (질문 + 키워드 결합)
        for item in self.faq_items:
            text = item.get("question", "") + " " + " ".join(item.get("keywords", []))
            tokens = self._tokenize(text)
            self.documents.append(tokens)
            self.vocab.update(tokens)

        # IDF 계산
        n_docs = len(self.documents)
        for term in self.vocab:
            doc_count = sum(1 for doc in self.documents if term in doc)
            self.idf[term] = math.log((n_docs + 1) / (doc_count + 1)) + 1

        # TF-IDF 벡터 계산
        for doc in self.documents:
            self.tfidf_vectors.append(self._compute_tfidf(doc))

    def _compute_tfidf(self, tokens: list[str]) -> dict[str, float]:
        """토큰 리스트의 TF-IDF 벡터를 계산한다."""
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        vector = {}
        for term, count in tf.items():
            tf_val = count / total
            idf_val = self.idf.get(term, 1.0)
            vector[term] = tf_val * idf_val
        return vector

    def _cosine_similarity(self, vec1: dict, vec2: dict) -> float:
        """두 TF-IDF 벡터의 코사인 유사도를 계산한다."""
        common_terms = set(vec1.keys()) & set(vec2.keys())
        if not common_terms:
            return 0.0

        dot_product = sum(vec1[t] * vec2[t] for t in common_terms)
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def find_best_match(self, query: str, category: str | None = None, top_k: int = 3) -> list[dict]:
        """질문과 가장 유사한 FAQ를 찾는다.

        Args:
            query: 사용자 질문
            category: 카테고리 필터 (None이면 전체 검색)
            top_k: 반환할 상위 결과 수

        Returns:
            [{"faq": FAQ dict, "score": 유사도}, ...] (점수 내림차순)
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        query_vector = self._compute_tfidf(query_tokens)

        results = []
        for i, item in enumerate(self.faq_items):
            if category and item.get("category") != category:
                continue

            score = self._cosine_similarity(query_vector, self.tfidf_vectors[i])
            if score > 0:
                results.append({"faq": item, "score": round(score, 4)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
