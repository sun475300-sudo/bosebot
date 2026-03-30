"""Tests for FlowAnalyzer - conversation flow analysis and visualization."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.flow_analyzer import FlowAnalyzer


@pytest.fixture
def analyzer(tmp_path):
    """Create a FlowAnalyzer with a temporary database."""
    db_path = os.path.join(str(tmp_path), "test_flow.db")
    fa = FlowAnalyzer(db_path=db_path)
    yield fa
    fa.close()


@pytest.fixture
def populated_analyzer(analyzer):
    """FlowAnalyzer populated with sample session data."""
    # Session 1: general -> tariff -> general
    analyzer.record_turn("s1", "general", query="hello", response_type="faq_match", satisfaction_score=0.9)
    analyzer.record_turn("s1", "tariff", query="tariff rate?", response_type="faq_match", satisfaction_score=0.8)
    analyzer.record_turn("s1", "general", query="thanks", response_type="faq_match", satisfaction_score=1.0)

    # Session 2: general -> tariff
    analyzer.record_turn("s2", "general", query="hi", response_type="faq_match", satisfaction_score=0.7)
    analyzer.record_turn("s2", "tariff", query="tax?", response_type="tfidf_match", satisfaction_score=0.5)

    # Session 3: tariff -> procedure -> tariff
    analyzer.record_turn("s3", "tariff", query="duty", response_type="faq_match", satisfaction_score=0.8)
    analyzer.record_turn("s3", "procedure", query="how to apply", response_type="faq_match", satisfaction_score=0.9)
    analyzer.record_turn("s3", "tariff", query="duty again", response_type="escalation", satisfaction_score=0.4)

    # Session 4: general -> tariff (same path as s2)
    analyzer.record_turn("s4", "general", query="greetings", response_type="faq_match", satisfaction_score=0.6)
    analyzer.record_turn("s4", "tariff", query="what tariff?", response_type="faq_match", satisfaction_score=0.7)

    return analyzer


class TestSessionFlowAnalysis:
    """Test session flow analysis."""

    def test_analyze_session_returns_category_sequence(self, populated_analyzer):
        path = populated_analyzer.analyze_session("s1")
        assert path == ["general", "tariff", "general"]

    def test_analyze_session_empty(self, analyzer):
        path = analyzer.analyze_session("nonexistent")
        assert path == []

    def test_analyze_session_single_turn(self, analyzer):
        analyzer.record_turn("single", "general", query="test")
        path = analyzer.analyze_session("single")
        assert path == ["general"]

    def test_record_turn_auto_increments_index(self, analyzer):
        analyzer.record_turn("test_idx", "a")
        analyzer.record_turn("test_idx", "b")
        analyzer.record_turn("test_idx", "c")
        path = analyzer.analyze_session("test_idx")
        assert path == ["a", "b", "c"]


class TestTransitionMatrix:
    """Test transition matrix computation."""

    def test_transition_matrix_structure(self, populated_analyzer):
        matrix = populated_analyzer.get_transition_matrix()
        assert isinstance(matrix, dict)
        # general -> tariff should exist (s1, s2, s4)
        assert "general" in matrix
        assert "tariff" in matrix["general"]

    def test_transition_matrix_counts(self, populated_analyzer):
        matrix = populated_analyzer.get_transition_matrix()
        # general -> tariff: s1, s2, s4 = 3
        assert matrix["general"]["tariff"] == 3
        # tariff -> general: s1 = 1
        assert matrix["tariff"]["general"] == 1
        # tariff -> procedure: s3 = 1
        assert matrix["tariff"]["procedure"] == 1
        # procedure -> tariff: s3 = 1
        assert matrix["procedure"]["tariff"] == 1

    def test_transition_matrix_empty(self, analyzer):
        matrix = analyzer.get_transition_matrix()
        assert matrix == {}

    def test_single_turn_sessions_no_transitions(self, analyzer):
        analyzer.record_turn("only_one", "general")
        matrix = analyzer.get_transition_matrix()
        assert matrix == {}


class TestDropOffDetection:
    """Test drop-off detection."""

    def test_drop_off_points(self, populated_analyzer):
        drop_offs = populated_analyzer.get_drop_off_points()
        # s1 ends at general, s2 ends at tariff, s3 ends at tariff, s4 ends at tariff
        assert drop_offs["general"] == 1
        assert drop_offs["tariff"] == 3

    def test_drop_off_empty(self, analyzer):
        drop_offs = analyzer.get_drop_off_points()
        assert drop_offs == {}

    def test_drop_off_single_turn(self, analyzer):
        analyzer.record_turn("x", "procedure")
        drop_offs = analyzer.get_drop_off_points()
        assert drop_offs == {"procedure": 1}


class TestCommonPaths:
    """Test common paths identification."""

    def test_common_paths_most_frequent(self, populated_analyzer):
        paths = populated_analyzer.get_common_paths(top_n=10)
        assert len(paths) > 0
        # The most common path should be ["general", "tariff"] (s2 and s4)
        top_path = paths[0]
        assert top_path["path"] == ["general", "tariff"]
        assert top_path["count"] == 2

    def test_common_paths_respects_top_n(self, populated_analyzer):
        paths = populated_analyzer.get_common_paths(top_n=1)
        assert len(paths) == 1

    def test_common_paths_empty(self, analyzer):
        paths = analyzer.get_common_paths()
        assert paths == []


class TestSankeyDataFormat:
    """Test Sankey data generation format."""

    def test_sankey_data_has_nodes_and_links(self, populated_analyzer):
        data = populated_analyzer.generate_sankey_data()
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["links"], list)

    def test_sankey_nodes_have_id_and_name(self, populated_analyzer):
        data = populated_analyzer.generate_sankey_data()
        for node in data["nodes"]:
            assert "id" in node
            assert "name" in node

    def test_sankey_links_have_source_target_value(self, populated_analyzer):
        data = populated_analyzer.generate_sankey_data()
        for link in data["links"]:
            assert "source" in link
            assert "target" in link
            assert "value" in link
            assert isinstance(link["value"], int)
            assert link["value"] > 0

    def test_sankey_links_reference_valid_nodes(self, populated_analyzer):
        data = populated_analyzer.generate_sankey_data()
        node_ids = {n["id"] for n in data["nodes"]}
        for link in data["links"]:
            assert link["source"] in node_ids
            assert link["target"] in node_ids

    def test_sankey_empty(self, analyzer):
        data = analyzer.generate_sankey_data()
        assert data["nodes"] == []
        assert data["links"] == []

    def test_sankey_data_json_serializable(self, populated_analyzer):
        data = populated_analyzer.generate_sankey_data()
        serialized = json.dumps(data)
        assert isinstance(serialized, str)


class TestFlowPaths:
    """Test get_flow_paths method."""

    def test_flow_paths_returns_sessions(self, populated_analyzer):
        paths = populated_analyzer.get_flow_paths(limit=100)
        assert len(paths) == 4
        for entry in paths:
            assert "session_id" in entry
            assert "path" in entry
            assert isinstance(entry["path"], list)

    def test_flow_paths_limit(self, populated_analyzer):
        paths = populated_analyzer.get_flow_paths(limit=2)
        assert len(paths) == 2


class TestAvgTurnsPerCategory:
    """Test average turns per starting category."""

    def test_avg_turns(self, populated_analyzer):
        avg = populated_analyzer.get_avg_turns_per_category()
        # Sessions starting with "general": s1 (3 turns), s2 (2 turns), s4 (2 turns) -> avg 2.33
        assert "general" in avg
        assert abs(avg["general"] - 2.33) < 0.1
        # Sessions starting with "tariff": s3 (3 turns) -> avg 3.0
        assert "tariff" in avg
        assert avg["tariff"] == 3.0

    def test_avg_turns_empty(self, analyzer):
        avg = analyzer.get_avg_turns_per_category()
        assert avg == {}


class TestSatisfactionByPath:
    """Test satisfaction by path."""

    def test_satisfaction_by_path(self, populated_analyzer):
        result = populated_analyzer.get_satisfaction_by_path()
        assert isinstance(result, list)
        assert len(result) > 0
        for entry in result:
            assert "path" in entry
            assert "avg_satisfaction" in entry
            assert "session_count" in entry

    def test_satisfaction_sorted_descending(self, populated_analyzer):
        result = populated_analyzer.get_satisfaction_by_path()
        scores = [r["avg_satisfaction"] for r in result]
        assert scores == sorted(scores, reverse=True)


class TestFlowReport:
    """Test comprehensive flow report."""

    def test_report_keys(self, populated_analyzer):
        report = populated_analyzer.generate_flow_report()
        assert "generated_at" in report
        assert "common_paths" in report
        assert "drop_off_points" in report
        assert "transition_matrix" in report
        assert "avg_turns_per_category" in report
        assert "satisfaction_by_path" in report
        assert "sankey_data" in report

    def test_report_json_serializable(self, populated_analyzer):
        report = populated_analyzer.generate_flow_report()
        serialized = json.dumps(report)
        assert isinstance(serialized, str)


class TestFlowAPIEndpoints:
    """Test API endpoints for flow analysis."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        """Create a test client with a patched FlowAnalyzer."""
        # Patch environment to avoid needing real config
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        monkeypatch.setenv("CHATBOT_RATE_LIMIT", "1000")

        # Import app after patching env
        import web_server
        db_path = os.path.join(str(tmp_path), "api_flow.db")
        fa = FlowAnalyzer(db_path=db_path)

        # Populate test data
        fa.record_turn("api_s1", "general", query="hi")
        fa.record_turn("api_s1", "tariff", query="rate?")
        fa.record_turn("api_s2", "procedure", query="how?")

        web_server.flow_analyzer = fa
        web_server.app.config["TESTING"] = True

        # Disable auth for testing
        original_require_auth = web_server.jwt_auth.require_auth

        def mock_require_auth(*args, **kwargs):
            def decorator(f):
                return f
            return decorator

        monkeypatch.setattr(web_server.jwt_auth, "require_auth", mock_require_auth)

        with web_server.app.test_client() as client:
            yield client

        fa.close()

    def test_sankey_endpoint(self, client):
        resp = client.get("/api/admin/flow/sankey")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "links" in data

    def test_paths_endpoint(self, client):
        resp = client.get("/api/admin/flow/paths")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "paths" in data

    def test_paths_endpoint_with_top_n(self, client):
        resp = client.get("/api/admin/flow/paths?top_n=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["paths"]) <= 1

    def test_dropoff_endpoint(self, client):
        resp = client.get("/api/admin/flow/dropoff")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "drop_off_points" in data

    def test_transitions_endpoint(self, client):
        resp = client.get("/api/admin/flow/transitions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "transitions" in data
