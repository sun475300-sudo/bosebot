"""Chart data generator tests."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.chart_data import ChartDataGenerator
from src.logger_db import ChatLogger
from src.feedback import FeedbackManager


@pytest.fixture
def gen(tmp_path):
    logger = ChatLogger(db_path=str(tmp_path / "logs.db"))
    feedback = FeedbackManager(db_path=str(tmp_path / "feedback.db"))
    return ChartDataGenerator(logger_db=logger, feedback_db=feedback)


class TestCategoryDistribution:
    def test_returns_chart_format(self, gen):
        result = gen.category_distribution()
        assert "type" in result
        assert "labels" in result
        assert "datasets" in result

    def test_type_is_pie(self, gen):
        assert gen.category_distribution()["type"] == "pie"

    def test_has_title(self, gen):
        assert "title" in gen.category_distribution()


class TestDailyQueryTrend:
    def test_returns_line_chart(self, gen):
        result = gen.daily_query_trend(days=7)
        assert result["type"] == "line"

    def test_labels_count(self, gen):
        result = gen.daily_query_trend(days=7)
        assert len(result["labels"]) == 7

    def test_datasets_exist(self, gen):
        result = gen.daily_query_trend(days=7)
        assert len(result["datasets"]) >= 1


class TestHourlyHeatmap:
    def test_returns_heatmap(self, gen):
        result = gen.hourly_heatmap(days=7)
        assert result["type"] == "heatmap"

    def test_has_data(self, gen):
        result = gen.hourly_heatmap(days=7)
        assert "datasets" in result


class TestTopQueries:
    def test_returns_bar_chart(self, gen):
        result = gen.top_queries(limit=10)
        assert result["type"] == "bar"

    def test_respects_limit(self, gen):
        result = gen.top_queries(limit=5)
        assert len(result["labels"]) <= 5


class TestSentimentDistribution:
    def test_returns_pie(self, gen):
        result = gen.sentiment_distribution()
        assert result["type"] == "pie"


class TestUserSegmentDistribution:
    def test_returns_pie(self, gen):
        result = gen.user_segment_distribution()
        assert result["type"] == "pie"


class TestChartAPI:
    @pytest.fixture
    def client(self):
        os.environ["ADMIN_AUTH_DISABLED"] = "true"
        os.environ["TESTING"] = "true"
        from web_server import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c
        os.environ.pop("ADMIN_AUTH_DISABLED", None)
        os.environ.pop("TESTING", None)

    def test_categories_endpoint(self, client):
        res = client.get("/api/admin/charts/categories")
        assert res.status_code == 200
        data = res.get_json()
        assert data["type"] == "pie"

    def test_trends_endpoint(self, client):
        res = client.get("/api/admin/charts/trends?metric=queries&days=7")
        assert res.status_code == 200

    def test_heatmap_endpoint(self, client):
        res = client.get("/api/admin/charts/heatmap")
        assert res.status_code == 200

    def test_dashboard_endpoint(self, client):
        res = client.get("/api/admin/charts/dashboard")
        assert res.status_code == 200
        data = res.get_json()
        assert "charts" in data
