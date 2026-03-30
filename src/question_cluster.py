"""질문 유사도 클러스터링 모듈.

FAQ 질문의 유사도를 분석하고 클러스터링하여 중복 감지 및 병합 제안을 수행한다.
"""

import math
from collections import Counter


class QuestionClusterer:
    """질문 유사도 기반 클러스터링 클래스."""

    def __init__(self, faq_items: list[dict], query_logs: list[dict] | None = None):
        """FAQ 데이터와 선택적 쿼리 로그로 초기화한다.

        Args:
            faq_items: FAQ 항목 리스트.
            query_logs: 쿼리 로그 리스트 (선택적).
        """
        self.faq_items = faq_items
        self.query_logs = query_logs or []
        self.idf: dict[str, float] = {}
        self.documents: list[list[str]] = []
        self.tfidf_vectors: list[dict[str, float]] = []
        self._clusters: list[list[int]] | None = None

        self._build_index()

    def _tokenize(self, text: str) -> list[str]:
        """공백 기반 토크나이즈.

        Args:
            text: 토크나이즈할 텍스트.

        Returns:
            토큰 리스트.
        """
        tokens = []
        for token in text.strip().lower().split():
            token = token.strip("?.,!·()\"'")
            if token and len(token) > 1:
                tokens.append(token)
        return tokens

    def _build_index(self) -> None:
        """FAQ 질문에서 TF-IDF 벡터를 구축한다."""
        self.documents = []
        for item in self.faq_items:
            question = item.get("question", "")
            keywords = item.get("keywords", [])
            text_parts = [question]
            text_parts.extend(keywords)
            tokens = self._tokenize(" ".join(text_parts))
            self.documents.append(tokens)

        num_docs = len(self.documents)
        if num_docs == 0:
            return

        # DF 계산
        df: dict[str, int] = {}
        for doc in self.documents:
            for token in set(doc):
                df[token] = df.get(token, 0) + 1

        # IDF 계산
        self.idf = {}
        for token, doc_freq in df.items():
            self.idf[token] = math.log((num_docs + 1) / (doc_freq + 1)) + 1

        # TF-IDF 벡터 계산
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

    def _vectorize_query(self, text: str) -> dict[str, float]:
        """텍스트를 TF-IDF 벡터로 변환한다.

        Args:
            text: 변환할 텍스트.

        Returns:
            TF-IDF 벡터 딕셔너리.
        """
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        doc_len = len(tokens)
        vector: dict[str, float] = {}
        for token, count in tf.items():
            tf_val = count / doc_len
            idf_val = self.idf.get(token, 1.0)
            vector[token] = tf_val * idf_val
        return vector

    def compute_similarity(self, q1: str, q2: str) -> float:
        """두 질문 간의 코사인 유사도를 계산한다.

        Args:
            q1: 첫 번째 질문 문자열.
            q2: 두 번째 질문 문자열.

        Returns:
            코사인 유사도 (0.0 ~ 1.0).
        """
        vec1 = self._vectorize_query(q1)
        vec2 = self._vectorize_query(q2)
        return self._cosine_similarity(vec1, vec2)

    def _cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        """두 벡터의 코사인 유사도를 계산한다.

        Args:
            vec1: 첫 번째 벡터.
            vec2: 두 번째 벡터.

        Returns:
            코사인 유사도 (0.0 ~ 1.0).
        """
        if not vec1 or not vec2:
            return 0.0

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

    def cluster_questions(self, questions: list[str] | None = None, threshold: float = 0.5) -> list[list[int]]:
        """유사한 질문을 클러스터링한다 (agglomerative 방식).

        Args:
            questions: 클러스터링할 질문 리스트. None이면 FAQ 질문 사용.
            threshold: 클러스터 병합 임계값.

        Returns:
            클러스터 리스트 (각 클러스터는 인덱스 리스트).
        """
        if questions is not None:
            vectors = [self._vectorize_query(q) for q in questions]
        else:
            vectors = list(self.tfidf_vectors)
            questions = [item.get("question", "") for item in self.faq_items]

        n = len(vectors)
        if n == 0:
            return []

        # 각 항목을 개별 클러스터로 초기화
        clusters: list[list[int]] = [[i] for i in range(n)]
        active = list(range(n))

        # Agglomerative 클러스터링
        changed = True
        while changed:
            changed = False
            best_sim = -1.0
            best_i = -1
            best_j = -1

            for idx_a in range(len(active)):
                for idx_b in range(idx_a + 1, len(active)):
                    ci = active[idx_a]
                    cj = active[idx_b]
                    # 평균 링크 유사도 계산
                    sim_sum = 0.0
                    count = 0
                    for a in clusters[ci]:
                        for b in clusters[cj]:
                            sim_sum += self._cosine_similarity(vectors[a], vectors[b])
                            count += 1
                    avg_sim = sim_sum / count if count > 0 else 0.0
                    if avg_sim > best_sim:
                        best_sim = avg_sim
                        best_i = ci
                        best_j = cj

            if best_sim >= threshold and best_i >= 0 and best_j >= 0:
                clusters[best_i].extend(clusters[best_j])
                clusters[best_j] = []
                active = [c for c in active if clusters[c]]
                changed = True

        self._clusters = [c for c in clusters if c]
        return self._clusters

    def find_duplicates(self, threshold: float = 0.7) -> list[dict]:
        """FAQ에서 유사도가 높은 중복 후보 쌍을 찾는다.

        Args:
            threshold: 중복 판단 임계값.

        Returns:
            중복 후보 리스트 [{index_a, index_b, question_a, question_b, similarity}].
        """
        duplicates = []
        n = len(self.tfidf_vectors)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._cosine_similarity(self.tfidf_vectors[i], self.tfidf_vectors[j])
                if sim >= threshold:
                    duplicates.append({
                        "index_a": i,
                        "index_b": j,
                        "question_a": self.faq_items[i].get("question", ""),
                        "question_b": self.faq_items[j].get("question", ""),
                        "similarity": round(sim, 4),
                    })
        duplicates.sort(key=lambda x: x["similarity"], reverse=True)
        return duplicates

    def suggest_merges(self) -> list[dict]:
        """FAQ 항목 중 병합 가능한 쌍을 제안한다 (유사도 > 0.6).

        Returns:
            병합 제안 리스트 [{index_a, index_b, question_a, question_b, similarity, reason}].
        """
        merges = []
        n = len(self.tfidf_vectors)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._cosine_similarity(self.tfidf_vectors[i], self.tfidf_vectors[j])
                if sim > 0.6:
                    item_a = self.faq_items[i]
                    item_b = self.faq_items[j]
                    same_category = item_a.get("category") == item_b.get("category")
                    reason = "같은 카테고리의 유사 질문" if same_category else "다른 카테고리이나 유사한 질문"
                    merges.append({
                        "index_a": i,
                        "index_b": j,
                        "question_a": item_a.get("question", ""),
                        "question_b": item_b.get("question", ""),
                        "similarity": round(sim, 4),
                        "same_category": same_category,
                        "reason": reason,
                    })
        merges.sort(key=lambda x: x["similarity"], reverse=True)
        return merges

    def get_cluster_stats(self) -> dict:
        """클러스터 통계를 반환한다.

        Returns:
            클러스터 통계 딕셔너리.
        """
        if self._clusters is None:
            self.cluster_questions()

        clusters = self._clusters or []
        sizes = [len(c) for c in clusters]
        if not sizes:
            return {
                "total_clusters": 0,
                "total_items": 0,
                "singleton_clusters": 0,
                "multi_item_clusters": 0,
                "largest_cluster_size": 0,
                "average_cluster_size": 0.0,
                "size_distribution": {},
                "largest_clusters": [],
            }

        size_dist: dict[int, int] = {}
        for s in sizes:
            size_dist[s] = size_dist.get(s, 0) + 1

        # 가장 큰 클러스터 상위 5개
        sorted_clusters = sorted(clusters, key=len, reverse=True)
        largest = []
        for c in sorted_clusters[:5]:
            questions = [self.faq_items[i].get("question", "") for i in c if i < len(self.faq_items)]
            largest.append({"size": len(c), "indices": c, "questions": questions})

        return {
            "total_clusters": len(clusters),
            "total_items": sum(sizes),
            "singleton_clusters": sum(1 for s in sizes if s == 1),
            "multi_item_clusters": sum(1 for s in sizes if s > 1),
            "largest_cluster_size": max(sizes),
            "average_cluster_size": round(sum(sizes) / len(sizes), 2),
            "size_distribution": size_dist,
            "largest_clusters": largest,
        }

    def find_similar_to(self, query: str, top_k: int = 5) -> list[dict]:
        """새 쿼리와 가장 유사한 기존 FAQ 질문을 찾는다.

        Args:
            query: 검색 쿼리.
            top_k: 반환할 최대 항목 수.

        Returns:
            유사 질문 리스트 [{index, question, similarity}].
        """
        query_vec = self._vectorize_query(query)
        if not query_vec:
            return []

        results = []
        for i, vec in enumerate(self.tfidf_vectors):
            sim = self._cosine_similarity(query_vec, vec)
            if sim > 0.0:
                results.append({
                    "index": i,
                    "question": self.faq_items[i].get("question", ""),
                    "id": self.faq_items[i].get("id", ""),
                    "category": self.faq_items[i].get("category", ""),
                    "similarity": round(sim, 4),
                })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


class DuplicateDetector:
    """FAQ 및 쿼리 로그에서 중복을 감지하는 클래스."""

    def __init__(self, faq_items: list[dict], query_logs: list[dict] | None = None):
        """초기화.

        Args:
            faq_items: FAQ 항목 리스트.
            query_logs: 쿼리 로그 리스트.
        """
        self.faq_items = faq_items
        self.query_logs = query_logs or []
        self.clusterer = QuestionClusterer(faq_items, query_logs)

    def detect_in_faq(self, threshold: float = 0.7) -> list[dict]:
        """FAQ에서 잠재적 중복을 탐지한다.

        Args:
            threshold: 중복 판단 임계값.

        Returns:
            중복 후보 리스트.
        """
        return self.clusterer.find_duplicates(threshold=threshold)

    def detect_in_logs(self, threshold: float = 0.7) -> list[dict]:
        """쿼리 로그에서 반복 질문을 탐지한다.

        Args:
            threshold: 중복 판단 임계값.

        Returns:
            반복 질문 그룹 리스트.
        """
        if not self.query_logs:
            return []

        queries = [log.get("query", "") for log in self.query_logs if log.get("query")]
        if not queries:
            return []

        # 쿼리 간 유사도 비교
        seen: set[int] = set()
        groups: list[dict] = []

        for i in range(len(queries)):
            if i in seen:
                continue
            group_indices = [i]
            vec_i = self.clusterer._vectorize_query(queries[i])
            for j in range(i + 1, len(queries)):
                if j in seen:
                    continue
                vec_j = self.clusterer._vectorize_query(queries[j])
                sim = self.clusterer._cosine_similarity(vec_i, vec_j)
                if sim >= threshold:
                    group_indices.append(j)
                    seen.add(j)
            if len(group_indices) > 1:
                seen.update(group_indices)
                groups.append({
                    "representative": queries[i],
                    "count": len(group_indices),
                    "queries": [queries[idx] for idx in group_indices],
                })

        groups.sort(key=lambda x: x["count"], reverse=True)
        return groups

    def generate_report(self) -> dict:
        """종합 중복 감지 리포트를 생성한다.

        Returns:
            리포트 딕셔너리.
        """
        faq_duplicates = self.detect_in_faq()
        log_duplicates = self.detect_in_logs()
        merge_suggestions = self.clusterer.suggest_merges()
        cluster_stats = self.clusterer.get_cluster_stats()

        return {
            "faq_duplicate_count": len(faq_duplicates),
            "faq_duplicates": faq_duplicates,
            "log_repeated_groups": len(log_duplicates),
            "log_duplicates": log_duplicates,
            "merge_suggestion_count": len(merge_suggestions),
            "merge_suggestions": merge_suggestions,
            "cluster_stats": cluster_stats,
        }
