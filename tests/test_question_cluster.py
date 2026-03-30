"""질문 유사도 클러스터링 테스트."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.question_cluster import QuestionClusterer, DuplicateDetector


# --- 테스트용 FAQ 데이터 ---

SAMPLE_FAQ = [
    {
        "id": "1",
        "category": "GENERAL",
        "question": "보세전시장이 무엇인가요?",
        "keywords": ["보세전시장", "정의", "개념"],
        "answer": "보세전시장은 외국물품을 전시할 수 있는 보세구역입니다.",
    },
    {
        "id": "2",
        "category": "GENERAL",
        "question": "보세전시장의 정의가 뭔가요?",
        "keywords": ["보세전시장", "정의", "뜻"],
        "answer": "보세전시장은 박람회 등의 운영을 위한 보세구역입니다.",
    },
    {
        "id": "3",
        "category": "IMPORT_EXPORT",
        "question": "물품 반입 신고는 어떻게 하나요?",
        "keywords": ["반입", "신고", "절차"],
        "answer": "세관장에게 반출입신고를 하셔야 합니다.",
    },
    {
        "id": "4",
        "category": "IMPORT_EXPORT",
        "question": "물품 반출 신고 절차가 궁금합니다",
        "keywords": ["반출", "신고", "절차"],
        "answer": "세관장에게 반출입신고를 하셔야 합니다.",
    },
    {
        "id": "5",
        "category": "SALES",
        "question": "전시 물품을 현장에서 판매할 수 있나요?",
        "keywords": ["판매", "현장판매", "직매"],
        "answer": "수입면허를 받기 전에는 인도할 수 없습니다.",
    },
    {
        "id": "6",
        "category": "TAX",
        "question": "관세 납부 방법은 어떻게 되나요?",
        "keywords": ["관세", "납부", "방법"],
        "answer": "관세는 은행 또는 온라인으로 납부할 수 있습니다.",
    },
]


@pytest.fixture
def clusterer():
    return QuestionClusterer(SAMPLE_FAQ)


@pytest.fixture
def detector():
    return DuplicateDetector(SAMPLE_FAQ)


# --- QuestionClusterer 테스트 ---


class TestComputeSimilarity:
    def test_identical_questions(self, clusterer):
        """동일 질문의 유사도는 1.0이어야 한다."""
        sim = clusterer.compute_similarity(
            "보세전시장이 무엇인가요?", "보세전시장이 무엇인가요?"
        )
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_similar_questions_high(self, clusterer):
        """유사한 질문은 높은 유사도를 가져야 한다 (키워드 공유)."""
        sim = clusterer.compute_similarity(
            "보세전시장 정의 개념", "보세전시장 정의 뜻"
        )
        assert sim > 0.3

    def test_different_questions_low(self, clusterer):
        """다른 주제의 질문은 낮은 유사도를 가져야 한다."""
        sim = clusterer.compute_similarity(
            "보세전시장이 무엇인가요?", "관세 납부 방법은 어떻게 되나요?"
        )
        assert sim < 0.5

    def test_empty_question(self, clusterer):
        """빈 질문의 유사도는 0.0이어야 한다."""
        sim = clusterer.compute_similarity("", "보세전시장이 무엇인가요?")
        assert sim == 0.0

    def test_both_empty(self, clusterer):
        """빈 질문 쌍의 유사도는 0.0이어야 한다."""
        sim = clusterer.compute_similarity("", "")
        assert sim == 0.0

    def test_similarity_is_symmetric(self, clusterer):
        """유사도는 대칭이어야 한다."""
        sim1 = clusterer.compute_similarity("물품 반입 신고", "반입 신고 절차")
        sim2 = clusterer.compute_similarity("반입 신고 절차", "물품 반입 신고")
        assert sim1 == pytest.approx(sim2, abs=0.001)


class TestClusterQuestions:
    def test_cluster_returns_list(self, clusterer):
        """클러스터 결과는 리스트여야 한다."""
        clusters = clusterer.cluster_questions()
        assert isinstance(clusters, list)

    def test_all_items_in_clusters(self, clusterer):
        """모든 항목이 클러스터에 포함되어야 한다."""
        clusters = clusterer.cluster_questions()
        all_indices = set()
        for c in clusters:
            all_indices.update(c)
        assert all_indices == set(range(len(SAMPLE_FAQ)))

    def test_high_threshold_many_clusters(self, clusterer):
        """높은 임계값은 더 많은 클러스터를 생성해야 한다."""
        clusters_high = clusterer.cluster_questions(threshold=0.95)
        clusters_low = clusterer.cluster_questions(threshold=0.1)
        assert len(clusters_high) >= len(clusters_low)

    def test_custom_questions(self, clusterer):
        """커스텀 질문 리스트를 클러스터링할 수 있어야 한다."""
        questions = ["보세전시장 정의", "보세전시장 뜻", "관세 납부"]
        clusters = clusterer.cluster_questions(questions=questions, threshold=0.3)
        assert isinstance(clusters, list)
        all_indices = set()
        for c in clusters:
            all_indices.update(c)
        assert all_indices == {0, 1, 2}

    def test_empty_list(self, clusterer):
        """빈 리스트는 빈 클러스터를 반환해야 한다."""
        clusters = clusterer.cluster_questions(questions=[])
        assert clusters == []


class TestFindDuplicates:
    def test_returns_list(self, clusterer):
        """중복 결과는 리스트여야 한다."""
        dupes = clusterer.find_duplicates()
        assert isinstance(dupes, list)

    def test_duplicate_structure(self, clusterer):
        """중복 항목은 올바른 구조를 가져야 한다."""
        dupes = clusterer.find_duplicates(threshold=0.3)
        if dupes:
            d = dupes[0]
            assert "index_a" in d
            assert "index_b" in d
            assert "question_a" in d
            assert "question_b" in d
            assert "similarity" in d
            assert d["similarity"] >= 0.3

    def test_sorted_by_similarity(self, clusterer):
        """결과는 유사도 내림차순이어야 한다."""
        dupes = clusterer.find_duplicates(threshold=0.1)
        for i in range(len(dupes) - 1):
            assert dupes[i]["similarity"] >= dupes[i + 1]["similarity"]

    def test_high_threshold_fewer_results(self, clusterer):
        """높은 임계값은 더 적은 결과를 반환해야 한다."""
        dupes_low = clusterer.find_duplicates(threshold=0.1)
        dupes_high = clusterer.find_duplicates(threshold=0.9)
        assert len(dupes_high) <= len(dupes_low)


class TestSuggestMerges:
    def test_returns_list(self, clusterer):
        """병합 제안은 리스트여야 한다."""
        merges = clusterer.suggest_merges()
        assert isinstance(merges, list)

    def test_merge_structure(self, clusterer):
        """병합 항목은 올바른 구조를 가져야 한다."""
        # Use a lower threshold FAQ to guarantee results
        faq = [
            {"id": "1", "question": "보세전시장 무엇", "keywords": ["보세전시장", "정의"]},
            {"id": "2", "question": "보세전시장 정의", "keywords": ["보세전시장", "정의", "뜻"]},
        ]
        c = QuestionClusterer(faq)
        merges = c.suggest_merges()
        if merges:
            m = merges[0]
            assert "index_a" in m
            assert "index_b" in m
            assert "similarity" in m
            assert "reason" in m
            assert m["similarity"] > 0.6

    def test_merge_similarity_above_threshold(self, clusterer):
        """병합 제안은 유사도 > 0.6이어야 한다."""
        merges = clusterer.suggest_merges()
        for m in merges:
            assert m["similarity"] > 0.6


class TestGetClusterStats:
    def test_stats_structure(self, clusterer):
        """통계는 올바른 키를 가져야 한다."""
        stats = clusterer.get_cluster_stats()
        assert "total_clusters" in stats
        assert "total_items" in stats
        assert "singleton_clusters" in stats
        assert "multi_item_clusters" in stats
        assert "largest_cluster_size" in stats
        assert "average_cluster_size" in stats
        assert "size_distribution" in stats
        assert "largest_clusters" in stats

    def test_total_items_matches(self, clusterer):
        """총 항목 수는 FAQ 크기와 일치해야 한다."""
        stats = clusterer.get_cluster_stats()
        assert stats["total_items"] == len(SAMPLE_FAQ)

    def test_singleton_plus_multi_equals_total(self, clusterer):
        """단일+다중 클러스터 = 전체 클러스터 수."""
        stats = clusterer.get_cluster_stats()
        assert stats["singleton_clusters"] + stats["multi_item_clusters"] == stats["total_clusters"]


class TestFindSimilarTo:
    def test_returns_list(self, clusterer):
        """유사 질문 결과는 리스트여야 한다."""
        results = clusterer.find_similar_to("보세전시장")
        assert isinstance(results, list)

    def test_top_k_limit(self, clusterer):
        """결과 수는 top_k 이하여야 한다."""
        results = clusterer.find_similar_to("보세전시장", top_k=2)
        assert len(results) <= 2

    def test_result_structure(self, clusterer):
        """결과 항목은 올바른 구조를 가져야 한다."""
        results = clusterer.find_similar_to("보세전시장")
        if results:
            r = results[0]
            assert "index" in r
            assert "question" in r
            assert "similarity" in r
            assert "id" in r

    def test_sorted_by_similarity(self, clusterer):
        """결과는 유사도 내림차순이어야 한다."""
        results = clusterer.find_similar_to("보세전시장 물품 신고")
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]

    def test_empty_query(self, clusterer):
        """빈 쿼리는 빈 결과를 반환해야 한다."""
        results = clusterer.find_similar_to("")
        assert results == []


# --- DuplicateDetector 테스트 ---


class TestDuplicateDetector:
    def test_detect_in_faq(self, detector):
        """FAQ 중복 감지가 동작해야 한다."""
        dupes = detector.detect_in_faq()
        assert isinstance(dupes, list)

    def test_detect_in_faq_with_threshold(self, detector):
        """임계값을 조절할 수 있어야 한다."""
        dupes_low = detector.detect_in_faq(threshold=0.1)
        dupes_high = detector.detect_in_faq(threshold=0.9)
        assert len(dupes_high) <= len(dupes_low)

    def test_detect_in_logs_empty(self, detector):
        """로그가 없으면 빈 결과를 반환해야 한다."""
        result = detector.detect_in_logs()
        assert result == []

    def test_detect_in_logs_with_data(self):
        """로그 데이터로 반복 질문을 감지해야 한다."""
        logs = [
            {"query": "보세전시장이 무엇인가요?"},
            {"query": "보세전시장 정의가 뭔가요?"},
            {"query": "보세전시장이 뭔가요?"},
            {"query": "관세 납부 방법"},
        ]
        detector = DuplicateDetector(SAMPLE_FAQ, query_logs=logs)
        groups = detector.detect_in_logs(threshold=0.3)
        assert isinstance(groups, list)

    def test_generate_report(self, detector):
        """리포트가 올바른 구조를 가져야 한다."""
        report = detector.generate_report()
        assert "faq_duplicate_count" in report
        assert "faq_duplicates" in report
        assert "log_repeated_groups" in report
        assert "log_duplicates" in report
        assert "merge_suggestion_count" in report
        assert "merge_suggestions" in report
        assert "cluster_stats" in report

    def test_generate_report_counts_match(self, detector):
        """리포트의 카운트가 리스트 길이와 일치해야 한다."""
        report = detector.generate_report()
        assert report["faq_duplicate_count"] == len(report["faq_duplicates"])
        assert report["log_repeated_groups"] == len(report["log_duplicates"])
        assert report["merge_suggestion_count"] == len(report["merge_suggestions"])


# --- API 엔드포인트 테스트 ---


class TestClusterAPI:
    @pytest.fixture
    def client(self):
        from web_server import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def auth_header(self):
        from src.auth import JWTAuth

        jwt = JWTAuth()
        token = jwt.generate_token({"sub": "admin", "role": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_clusters_endpoint(self, client, auth_header):
        """클러스터 엔드포인트가 200을 반환해야 한다."""
        res = client.get("/api/admin/clusters", headers=auth_header)
        assert res.status_code == 200
        data = res.get_json()
        assert "clusters" in data
        assert "stats" in data

    def test_duplicates_endpoint(self, client, auth_header):
        """중복 감지 엔드포인트가 200을 반환해야 한다."""
        res = client.get("/api/admin/duplicates", headers=auth_header)
        assert res.status_code == 200
        data = res.get_json()
        assert "faq_duplicate_count" in data

    def test_similar_endpoint(self, client, auth_header):
        """유사 질문 검색 엔드포인트가 200을 반환해야 한다."""
        res = client.get(
            "/api/admin/similar?q=보세전시장", headers=auth_header
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "query" in data
        assert "results" in data
        assert data["query"] == "보세전시장"

    def test_similar_endpoint_missing_query(self, client, auth_header):
        """q 파라미터가 없으면 400을 반환해야 한다."""
        res = client.get("/api/admin/similar", headers=auth_header)
        assert res.status_code == 400

    def test_clusters_refresh_endpoint(self, client, auth_header):
        """클러스터 재계산 엔드포인트가 200을 반환해야 한다."""
        res = client.post("/api/admin/clusters/refresh", headers=auth_header)
        assert res.status_code == 200
        data = res.get_json()
        assert "message" in data
        assert "clusters" in data

    def test_clusters_endpoint_no_auth(self, client):
        """인증 없이 접근하면 401을 반환해야 한다."""
        from flask import Flask
        from web_server import app

        app.config["AUTH_TESTING"] = True
        try:
            res = client.get("/api/admin/clusters")
            assert res.status_code == 401
        finally:
            app.config["AUTH_TESTING"] = False


class TestEdgeCases:
    def test_empty_faq(self):
        """빈 FAQ로 초기화할 수 있어야 한다."""
        c = QuestionClusterer([])
        assert c.cluster_questions() == []
        assert c.find_duplicates() == []
        assert c.suggest_merges() == []
        assert c.find_similar_to("test") == []

    def test_single_item_faq(self):
        """단일 FAQ로 동작해야 한다."""
        faq = [{"id": "1", "question": "테스트 질문", "keywords": ["테스트"]}]
        c = QuestionClusterer(faq)
        clusters = c.cluster_questions()
        assert len(clusters) == 1
        assert clusters[0] == [0]

    def test_no_keywords(self):
        """키워드 없는 FAQ도 동작해야 한다."""
        faq = [{"id": "1", "question": "보세전시장이란?"}]
        c = QuestionClusterer(faq)
        results = c.find_similar_to("보세전시장")
        assert isinstance(results, list)
