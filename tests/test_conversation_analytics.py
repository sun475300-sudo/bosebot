"""ConversationAnalytics 및 PatternDetector 테스트."""

import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.conversation_analytics import ConversationAnalytics, PatternDetector
from src.feedback import FeedbackManager
from src.logger_db import ChatLogger


@pytest.fixture
def temp_dbs():
    """임시 DB 파일로 ChatLogger와 FeedbackManager를 생성한다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_db = ChatLogger(db_path=os.path.join(tmpdir, "chat_logs.db"))
        fb_db = FeedbackManager(db_path=os.path.join(tmpdir, "feedback.db"))
        yield log_db, fb_db
        log_db.close()
        fb_db.close()


@pytest.fixture
def analytics(temp_dbs):
    """빈 DB로 ConversationAnalytics 인스턴스를 생성한다."""
    log_db, fb_db = temp_dbs
    return ConversationAnalytics(log_db, fb_db)


@pytest.fixture
def analytics_with_data(temp_dbs):
    """데이터가 있는 ConversationAnalytics 인스턴스를 생성한다."""
    log_db, fb_db = temp_dbs

    # 세션 1: 여러 질문 (연속 타임스탬프)
    conn = log_db._get_conn()
    now = datetime.now()
    base = now - timedelta(hours=2)
    queries = [
        (base.strftime("%Y-%m-%d %H:%M:%S"),
         "보세전시장이 무엇인가요?", "GENERAL", "FAQ_001", 0),
        ((base + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"),
         "물품 반입 절차는?", "IMPORT_EXPORT", "FAQ_002", 0),
        ((base + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
         "관세 납부 방법은?", "TAX", None, 0),
    ]
    # 세션 2: 단일 질문 (이탈)
    base2 = now - timedelta(hours=1)
    queries.append(
        (base2.strftime("%Y-%m-%d %H:%M:%S"),
         "담당자와 통화하고 싶습니다", "GENERAL", None, 1),
    )
    # 세션 3: 여러 질문
    base3 = now
    queries.append(
        (base3.strftime("%Y-%m-%d %H:%M:%S"),
         "전시 기간은 얼마나 되나요?", "EXHIBITION", "FAQ_003", 0),
    )
    queries.append(
        ((base3 + timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S"),
         "보세전시장이 무엇인가요?", "GENERAL", "FAQ_001", 0),
    )

    for ts, query, cat, faq_id, esc in queries:
        conn.execute(
            """INSERT INTO chat_logs
               (timestamp, query, category, faq_id, is_escalation, response_preview)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ts, query, cat, faq_id, esc, None),
        )
    conn.commit()

    # 피드백 데이터
    fb_db.save_feedback("Q1", "helpful")
    fb_db.save_feedback("Q2", "helpful")
    fb_db.save_feedback("Q3", "unhelpful")
    fb_db.save_feedback("Q4", "helpful")

    return ConversationAnalytics(log_db, fb_db)


@pytest.fixture
def pattern_detector(temp_dbs):
    """PatternDetector 인스턴스를 생성한다."""
    log_db, fb_db = temp_dbs

    # 반복 패턴이 있는 데이터 삽입
    conn = log_db._get_conn()
    now = datetime.now()
    entries = [
        ("GENERAL",), ("IMPORT_EXPORT",), ("TAX",),
        ("GENERAL",), ("IMPORT_EXPORT",), ("TAX",),
        ("GENERAL",), ("EXHIBITION",),
    ]
    for i, (cat,) in enumerate(entries):
        ts = (now - timedelta(minutes=len(entries) - i)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        conn.execute(
            """INSERT INTO chat_logs
               (timestamp, query, category, faq_id, is_escalation)
               VALUES (?, ?, ?, ?, ?)""",
            (ts, f"질문 {i}", cat, None, 0),
        )
    conn.commit()

    return PatternDetector(log_db)


# ─── PatternDetector 테스트 ───────────────────────────────────────────────


class TestPatternDetectorInit:
    def test_init(self, temp_dbs):
        log_db, _ = temp_dbs
        pd = PatternDetector(log_db)
        assert pd.logger_db is log_db


class TestFindCommonSequences:
    def test_empty_db(self, temp_dbs):
        log_db, _ = temp_dbs
        pd = PatternDetector(log_db)
        result = pd.find_common_sequences()
        assert result == []

    def test_with_data(self, pattern_detector):
        result = pattern_detector.find_common_sequences(min_length=2)
        assert len(result) > 0
        for item in result:
            assert "sequence" in item
            assert "count" in item
            assert item["count"] >= 2
            assert len(item["sequence"]) >= 2

    def test_min_length_filter(self, pattern_detector):
        result = pattern_detector.find_common_sequences(min_length=3)
        for item in result:
            assert len(item["sequence"]) >= 3

    def test_sorted_by_count(self, pattern_detector):
        result = pattern_detector.find_common_sequences(min_length=2)
        if len(result) >= 2:
            for i in range(len(result) - 1):
                assert result[i]["count"] >= result[i + 1]["count"]


class TestFindQuestionPairs:
    def test_empty_db(self, temp_dbs):
        log_db, _ = temp_dbs
        pd = PatternDetector(log_db)
        result = pd.find_question_pairs()
        assert result == []

    def test_with_data(self, pattern_detector):
        result = pattern_detector.find_question_pairs()
        assert len(result) > 0
        for item in result:
            assert "pair" in item
            assert "count" in item
            assert len(item["pair"]) == 2

    def test_contains_repeated_pair(self, pattern_detector):
        """반복되는 (GENERAL, IMPORT_EXPORT) 쌍이 있어야 한다."""
        result = pattern_detector.find_question_pairs()
        gi_pairs = [
            p for p in result
            if p["pair"] == ["GENERAL", "IMPORT_EXPORT"]
        ]
        assert len(gi_pairs) == 1
        assert gi_pairs[0]["count"] >= 2


class TestDetectSeasonality:
    def test_empty_db(self, temp_dbs):
        log_db, _ = temp_dbs
        pd = PatternDetector(log_db)
        result = pd.detect_seasonality()
        assert "weekday_distribution" in result
        assert "weekly_trend" in result
        assert result["busiest_day"] is None
        assert result["quietest_day"] is None

    def test_with_data(self, pattern_detector):
        result = pattern_detector.detect_seasonality()
        assert result["busiest_day"] is not None
        assert result["quietest_day"] is not None
        assert isinstance(result["weekday_distribution"], dict)
        assert len(result["weekday_distribution"]) == 7

    def test_weekly_trend_structure(self, pattern_detector):
        result = pattern_detector.detect_seasonality()
        for item in result["weekly_trend"]:
            assert "week" in item
            assert "count" in item


# ─── ConversationAnalytics 테스트 ─────────────────────────────────────────


class TestConversationAnalyticsInit:
    def test_init(self, temp_dbs):
        log_db, fb_db = temp_dbs
        ca = ConversationAnalytics(log_db, fb_db)
        assert ca.logger_db is log_db
        assert ca.feedback_db is fb_db
        assert isinstance(ca.pattern_detector, PatternDetector)


class TestDetectPatterns:
    def test_empty_db(self, analytics):
        result = analytics.detect_patterns(days=30)
        assert result["days"] == 30
        assert result["recurring_queries"] == []
        assert result["category_patterns"] == []
        assert result["top_queries"] == []

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.detect_patterns(days=30)
        assert result["days"] == 30
        assert len(result["category_patterns"]) > 0
        assert len(result["top_queries"]) > 0

    def test_recurring_queries_detected(self, analytics_with_data):
        """'보세전시장이 무엇인가요?'가 2회 등장하므로 반복 질문으로 탐지."""
        result = analytics_with_data.detect_patterns(days=30)
        queries = [q["query"] for q in result["recurring_queries"]]
        assert "보세전시장이 무엇인가요?" in queries

    def test_custom_days(self, analytics_with_data):
        result = analytics_with_data.detect_patterns(days=7)
        assert result["days"] == 7


class TestGetAbandonRate:
    def test_empty_db(self, analytics):
        result = analytics.get_abandon_rate()
        assert result["abandon_rate"] == 0.0
        assert result["total_sessions"] == 0
        assert result["abandoned_sessions"] == 0

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_abandon_rate()
        assert result["total_sessions"] >= 1
        assert 0 <= result["abandon_rate"] <= 100
        assert result["abandoned_sessions"] >= 0

    def test_abandon_rate_calculation(self, analytics_with_data):
        """세션 3개 중 1개가 이탈 (단일 질문) -> ~33%."""
        result = analytics_with_data.get_abandon_rate()
        assert result["total_sessions"] == 3
        assert result["abandoned_sessions"] == 1
        assert abs(result["abandon_rate"] - 33.3) < 0.2


class TestGetResolutionRate:
    def test_empty_db(self, analytics):
        result = analytics.get_resolution_rate()
        assert result["resolution_rate"] == 0.0
        assert result["total_feedback"] == 0
        assert result["helpful_count"] == 0

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_resolution_rate()
        assert result["total_feedback"] == 4
        assert result["helpful_count"] == 3
        assert result["resolution_rate"] == 75.0


class TestGetAvgSessionDuration:
    def test_empty_db(self, analytics):
        result = analytics.get_avg_session_duration()
        assert result["avg_duration_seconds"] == 0.0
        assert result["total_sessions"] == 0

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_avg_session_duration()
        assert result["total_sessions"] >= 1
        assert result["avg_duration_seconds"] >= 0
        assert result["max_duration"] >= result["min_duration"]

    def test_structure(self, analytics_with_data):
        result = analytics_with_data.get_avg_session_duration()
        assert "avg_duration_seconds" in result
        assert "total_sessions" in result
        assert "max_duration" in result
        assert "min_duration" in result


class TestGetRepeatVisitorRate:
    def test_empty_db(self, analytics):
        result = analytics.get_repeat_visitor_rate()
        assert result["repeat_rate"] == 0.0
        assert result["total_unique_queries"] == 0

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_repeat_visitor_rate()
        assert result["total_unique_queries"] > 0
        assert 0 <= result["repeat_rate"] <= 100


class TestGetQuestionDifficultyRanking:
    def test_empty_db(self, analytics):
        result = analytics.get_question_difficulty_ranking()
        assert result == []

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_question_difficulty_ranking()
        assert len(result) > 0
        for item in result:
            assert "category" in item
            assert "difficulty_score" in item
            assert "match_rate" in item
            assert "escalation_rate" in item
            assert "total_queries" in item

    def test_sorted_by_difficulty(self, analytics_with_data):
        result = analytics_with_data.get_question_difficulty_ranking()
        if len(result) >= 2:
            for i in range(len(result) - 1):
                assert result[i]["difficulty_score"] >= result[i + 1]["difficulty_score"]

    def test_unmatched_category_harder(self, analytics_with_data):
        """FAQ 매칭이 안 된 카테고리가 더 어려워야 한다."""
        result = analytics_with_data.get_question_difficulty_ranking()
        # TAX 카테고리는 faq_id=None이므로 난이도가 높아야 한다
        tax_items = [r for r in result if r["category"] == "TAX"]
        if tax_items:
            assert tax_items[0]["match_rate"] == 0.0
            assert tax_items[0]["difficulty_score"] > 0


class TestGetPeakUsagePatterns:
    def test_empty_db(self, analytics):
        result = analytics.get_peak_usage_patterns()
        assert "hourly" in result
        assert "by_day_of_week" in result
        assert "peak_hour" in result
        assert "peak_day" in result
        assert "heatmap" in result

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_peak_usage_patterns()
        total = sum(result["hourly"].values())
        assert total == 6

    def test_heatmap_structure(self, analytics_with_data):
        result = analytics_with_data.get_peak_usage_patterns()
        assert len(result["heatmap"]) == 7 * 24
        for item in result["heatmap"]:
            assert "day" in item
            assert "hour" in item
            assert "count" in item

    def test_day_totals(self, analytics_with_data):
        result = analytics_with_data.get_peak_usage_patterns()
        assert isinstance(result["day_totals"], dict)
        assert sum(result["day_totals"].values()) == 6


class TestGenerateInsights:
    def test_empty_db(self, analytics):
        result = analytics.generate_insights(days=30)
        assert "insights" in result
        assert "generated_at" in result
        assert "summary" in result
        assert isinstance(result["insights"], list)

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.generate_insights(days=30)
        assert len(result["insights"]) > 0
        assert "generated_at" in result

    def test_insights_are_strings(self, analytics_with_data):
        result = analytics_with_data.generate_insights(days=30)
        for insight in result["insights"]:
            assert isinstance(insight, str)
            assert len(insight) > 10

    def test_metrics_included(self, analytics_with_data):
        result = analytics_with_data.generate_insights(days=30)
        assert "metrics" in result
        assert "abandon_rate" in result["metrics"]
        assert "resolution_rate" in result["metrics"]

    def test_summary_text(self, analytics_with_data):
        result = analytics_with_data.generate_insights(days=30)
        assert "sessions" in result["summary"]


class TestGetAllMetrics:
    def test_empty_db(self, analytics):
        result = analytics.get_all_metrics()
        assert "abandon" in result
        assert "resolution" in result
        assert "session_duration" in result
        assert "repeat_visitor" in result
        assert "difficulty_ranking" in result
        assert "peak_usage" in result

    def test_with_data(self, analytics_with_data):
        result = analytics_with_data.get_all_metrics()
        assert result["abandon"]["total_sessions"] >= 1
        assert result["resolution"]["total_feedback"] == 4
        assert result["session_duration"]["total_sessions"] >= 1
        assert len(result["difficulty_ranking"]) > 0


class TestBuildSessions:
    def test_empty_db(self, analytics):
        sessions = analytics._build_sessions()
        assert sessions == []

    def test_with_data(self, analytics_with_data):
        sessions = analytics_with_data._build_sessions()
        assert len(sessions) == 3

    def test_session_structure(self, analytics_with_data):
        sessions = analytics_with_data._build_sessions()
        for s in sessions:
            assert "session_start" in s
            assert "session_end" in s
            assert "query_count" in s
            assert "duration_seconds" in s
            assert s["query_count"] >= 1
            assert s["duration_seconds"] >= 0


# ─── API 엔드포인트 테스트 ───────────────────────────────────────────────

class TestAPIEndpoints:
    @pytest.fixture
    def client(self):
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_patterns_endpoint_returns_ok(self, client):
        """패턴 분석 엔드포인트가 정상 응답을 반환한다."""
        res = client.get("/api/admin/analytics/patterns")
        assert res.status_code == 200
        data = res.get_json()
        assert "patterns" in data
        assert "sequences" in data
        assert "pairs" in data
        assert "seasonality" in data

    def test_insights_endpoint_returns_ok(self, client):
        """인사이트 엔드포인트가 정상 응답을 반환한다."""
        res = client.get("/api/admin/analytics/insights")
        assert res.status_code == 200
        data = res.get_json()
        assert "insights" in data
        assert "generated_at" in data

    def test_metrics_endpoint_returns_ok(self, client):
        """분석 지표 엔드포인트가 정상 응답을 반환한다."""
        res = client.get("/api/admin/analytics/metrics")
        assert res.status_code == 200
        data = res.get_json()
        assert "abandon" in data
        assert "resolution" in data
        assert "session_duration" in data

    def test_patterns_with_days_param(self, client):
        """days 파라미터가 정상 동작한다."""
        res = client.get("/api/admin/analytics/patterns?days=7")
        assert res.status_code == 200
        data = res.get_json()
        assert data["patterns"]["days"] == 7

    def test_insights_with_days_param(self, client):
        res = client.get("/api/admin/analytics/insights?days=14")
        assert res.status_code == 200

    def test_endpoints_not_404(self, client):
        """모든 엔드포인트가 등록되어 있다."""
        for path in [
            "/api/admin/analytics/patterns",
            "/api/admin/analytics/insights",
            "/api/admin/analytics/metrics",
        ]:
            res = client.get(path)
            assert res.status_code != 404, f"{path} returned 404"
