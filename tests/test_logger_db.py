"""ChatLogger SQLite 로그 시스템 테스트."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger_db import ChatLogger


@pytest.fixture
def logger():
    """임시 DB 파일로 ChatLogger 인스턴스를 생성한다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_logs.db")
        chat_logger = ChatLogger(db_path=db_path)
        yield chat_logger
        chat_logger.close()


class TestLogQuery:
    """로그 저장/조회 테스트."""

    def test_log_single_query(self, logger):
        logger.log_query(
            query="보세전시장이란?",
            category="DEFINITION",
            faq_id="FAQ001",
            is_escalation=False,
            response_preview="보세전시장은 관세법 제190조에 의한 장소입니다.",
        )
        logs = logger.get_recent_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]["query"] == "보세전시장이란?"
        assert logs[0]["category"] == "DEFINITION"
        assert logs[0]["faq_id"] == "FAQ001"
        assert logs[0]["is_escalation"] == 0

    def test_log_multiple_queries(self, logger):
        for i in range(5):
            logger.log_query(query=f"질문 {i}", category="TEST")
        logs = logger.get_recent_logs(limit=10)
        assert len(logs) == 5

    def test_log_escalation(self, logger):
        logger.log_query(
            query="시스템 오류",
            category="TECH",
            is_escalation=True,
        )
        logs = logger.get_recent_logs(limit=1)
        assert logs[0]["is_escalation"] == 1

    def test_log_without_faq_id(self, logger):
        logger.log_query(query="알 수 없는 질문", category="GENERAL")
        logs = logger.get_recent_logs(limit=1)
        assert logs[0]["faq_id"] is None

    def test_response_preview_truncated(self, logger):
        long_response = "A" * 500
        logger.log_query(
            query="긴 응답 테스트",
            category="TEST",
            response_preview=long_response,
        )
        logs = logger.get_recent_logs(limit=1)
        assert len(logs[0]["response_preview"]) == 200

    def test_recent_logs_order(self, logger):
        logger.log_query(query="첫 번째", category="A")
        logger.log_query(query="두 번째", category="B")
        logger.log_query(query="세 번째", category="C")
        logs = logger.get_recent_logs(limit=10)
        assert logs[0]["query"] == "세 번째"
        assert logs[2]["query"] == "첫 번째"

    def test_recent_logs_limit(self, logger):
        for i in range(10):
            logger.log_query(query=f"질문 {i}", category="TEST")
        logs = logger.get_recent_logs(limit=3)
        assert len(logs) == 3

    def test_timestamp_format(self, logger):
        logger.log_query(query="시간 테스트", category="TEST")
        logs = logger.get_recent_logs(limit=1)
        ts = logs[0]["timestamp"]
        # YYYY-MM-DD HH:MM:SS
        assert len(ts) == 19
        assert ts[4] == "-"
        assert ts[10] == " "


class TestStats:
    """통계 계산 테스트."""

    def test_empty_stats(self, logger):
        stats = logger.get_stats()
        assert stats["total_queries"] == 0
        assert stats["today_queries"] == 0
        assert stats["escalation_rate"] == 0
        assert stats["unmatched_rate"] == 0
        assert stats["category_distribution"] == {}

    def test_total_count(self, logger):
        for i in range(7):
            logger.log_query(query=f"질문 {i}", category="TEST")
        stats = logger.get_stats()
        assert stats["total_queries"] == 7

    def test_today_count(self, logger):
        # 오늘 날짜로 저장되므로 today_queries도 같아야 함
        for i in range(3):
            logger.log_query(query=f"질문 {i}", category="TEST")
        stats = logger.get_stats()
        assert stats["today_queries"] == 3

    def test_category_distribution(self, logger):
        logger.log_query(query="Q1", category="DEFINITION")
        logger.log_query(query="Q2", category="DEFINITION")
        logger.log_query(query="Q3", category="SALES")
        logger.log_query(query="Q4", category="PROCEDURE")
        stats = logger.get_stats()
        dist = stats["category_distribution"]
        assert dist["DEFINITION"] == 2
        assert dist["SALES"] == 1
        assert dist["PROCEDURE"] == 1

    def test_escalation_rate(self, logger):
        logger.log_query(query="Q1", category="A", is_escalation=True)
        logger.log_query(query="Q2", category="A", is_escalation=False)
        logger.log_query(query="Q3", category="A", is_escalation=False)
        logger.log_query(query="Q4", category="A", is_escalation=True)
        stats = logger.get_stats()
        assert stats["escalation_rate"] == 50.0

    def test_unmatched_rate(self, logger):
        logger.log_query(query="Q1", category="A", faq_id="FAQ001")
        logger.log_query(query="Q2", category="A", faq_id=None)
        logger.log_query(query="Q3", category="A", faq_id=None)
        stats = logger.get_stats()
        # 2/3 = 66.7%
        assert stats["unmatched_rate"] == 66.7


class TestUnmatchedQueries:
    """미매칭 질문 필터링 테스트."""

    def test_returns_only_unmatched(self, logger):
        logger.log_query(query="매칭됨", category="A", faq_id="FAQ001")
        logger.log_query(query="미매칭1", category="B", faq_id=None)
        logger.log_query(query="미매칭2", category="C", faq_id=None)
        unmatched = logger.get_unmatched_queries(limit=10)
        assert len(unmatched) == 2
        queries = [q["query"] for q in unmatched]
        assert "매칭됨" not in queries
        assert "미매칭1" in queries
        assert "미매칭2" in queries

    def test_unmatched_limit(self, logger):
        for i in range(10):
            logger.log_query(query=f"미매칭 {i}", category="A")
        unmatched = logger.get_unmatched_queries(limit=3)
        assert len(unmatched) == 3

    def test_unmatched_order_desc(self, logger):
        logger.log_query(query="오래된 질문", category="A")
        logger.log_query(query="최신 질문", category="B")
        unmatched = logger.get_unmatched_queries(limit=10)
        assert unmatched[0]["query"] == "최신 질문"

    def test_unmatched_has_required_fields(self, logger):
        logger.log_query(query="테스트", category="X")
        unmatched = logger.get_unmatched_queries(limit=1)
        item = unmatched[0]
        assert "query" in item
        assert "category" in item
        assert "timestamp" in item

    def test_no_unmatched_when_all_matched(self, logger):
        logger.log_query(query="Q1", category="A", faq_id="FAQ001")
        logger.log_query(query="Q2", category="B", faq_id="FAQ002")
        unmatched = logger.get_unmatched_queries(limit=10)
        assert len(unmatched) == 0


class TestDbInit:
    """DB 초기화 테스트."""

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub", "dir", "test.db")
            chat_logger = ChatLogger(db_path=nested)
            assert os.path.isdir(os.path.join(tmpdir, "sub", "dir"))
            chat_logger.close()

    def test_close_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            logger1 = ChatLogger(db_path=db_path)
            logger1.log_query(query="영속성 테스트", category="TEST")
            logger1.close()

            logger2 = ChatLogger(db_path=db_path)
            logs = logger2.get_recent_logs(limit=10)
            assert len(logs) == 1
            assert logs[0]["query"] == "영속성 테스트"
            logger2.close()
