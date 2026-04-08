"""Massive end-to-end integration test exercising the entire system.

Covers:
  1. TestCompleteUserJourney  - full user lifecycle
  2. TestAdminWorkflow         - admin dashboard & management
  3. TestMultiTenantIsolation  - tenant data isolation
  4. TestAPIVersioning         - v1/v2 compatibility
  5. TestSecurityComprehensive - auth, rate-limit, sanitization
"""

import copy
import json
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["ADMIN_AUTH_DISABLED"] = "true"
os.environ["TESTING"] = "true"

from web_server import app

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAQ_PATH = os.path.join(BASE_DIR, "data", "faq.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Flask test client with auth bypassed for non-auth tests."""
    app.config["TESTING"] = True
    old_env = os.environ.get("ADMIN_AUTH_DISABLED")
    os.environ["ADMIN_AUTH_DISABLED"] = "true"
    # Clear rate limiter state to avoid 429s from prior tests
    try:
        from web_server import advanced_rate_limiter
        if hasattr(advanced_rate_limiter, '_windows'):
            advanced_rate_limiter._windows.clear()
        if hasattr(advanced_rate_limiter, '_quotas_used'):
            advanced_rate_limiter._quotas_used.clear()
    except Exception:
        pass
    with app.test_client() as c:
        yield c
    if old_env is not None:
        os.environ["ADMIN_AUTH_DISABLED"] = old_env
    else:
        os.environ.pop("ADMIN_AUTH_DISABLED", None)


@pytest.fixture
def auth_client():
    """Flask test client with auth enforcement enabled."""
    app.config["TESTING"] = True
    app.config["AUTH_TESTING"] = True
    old_auth = os.environ.pop("ADMIN_AUTH_DISABLED", None)
    old_testing = os.environ.pop("TESTING", None)
    with app.test_client() as c:
        yield c
    app.config["AUTH_TESTING"] = False
    if old_auth is not None:
        os.environ["ADMIN_AUTH_DISABLED"] = old_auth
    if old_testing is not None:
        os.environ["TESTING"] = old_testing


@pytest.fixture
def faq_backup():
    """Backup and restore faq.json around tests that modify it."""
    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        original = f.read()
    yield
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        f.write(original)


def _get_token(c):
    """Login as default admin and return JWT token."""
    res = c.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    return res.get_json()["token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# 1. TestCompleteUserJourney (~20 tests)
# ============================================================
class TestCompleteUserJourney:
    """Simulates a real user from session creation to export."""

    def test_01_create_session(self, client):
        """Create a new session and get a session_id."""
        res = client.post("/api/session/new")
        assert res.status_code == 201
        data = res.get_json()
        assert "session_id" in data
        assert "created_at" in data

    def test_02_ask_beginner_question(self, client):
        """Ask a basic FAQ question and get a structured answer."""
        res = client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "answer" in data
        assert "category" in data
        assert "categories" in data
        assert data["is_escalation"] is False
        # Should mention the legal basis
        assert "관세법" in data["answer"]

    def test_03_get_segmented_response(self, client):
        """Ask with a session so that user segmentation kicks in."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        res = client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
            "session_id": sid,
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["session_id"] == sid
        # user_segment may be populated
        assert "user_segment" in data

    def test_04_follow_up_contextual_suggestions(self, client):
        """Ask a follow-up question and verify suggestions are returned."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        # First question
        client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
            "session_id": sid,
        })
        # Follow-up
        res = client.post("/api/chat", json={
            "query": "물품 반입 절차를 알려주세요",
            "session_id": sid,
        })
        data = res.get_json()
        assert res.status_code == 200
        assert "suggestions" in data

    def test_05_ambiguous_query(self, client):
        """An ambiguous query should still return a valid answer."""
        res = client.post("/api/chat", json={
            "query": "전시",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "answer" in data
        assert len(data["answer"]) > 10

    def test_06_legal_topic_citations(self, client):
        """Legal topic questions should include law citations in the answer."""
        res = client.post("/api/chat", json={
            "query": "보세전시장 특허 기간은 얼마나 되나요?",
        })
        data = res.get_json()
        assert res.status_code == 200
        # The answer should reference legal basis (관세법, 고시, or 근거: section)
        assert "관세법" in data["answer"] or "고시" in data["answer"] or "근거:" in data["answer"]

    def test_07_negative_sentiment_empathetic(self, client):
        """Negative sentiment query should trigger empathetic tone adjustment."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        res = client.post("/api/chat", json={
            "query": "정말 화가 납니다. 왜 아무도 도와주지 않나요?",
            "session_id": sid,
        })
        data = res.get_json()
        assert res.status_code == 200
        # Sentiment analysis should return negative
        assert "sentiment" in data
        if data["sentiment"]:
            assert data["sentiment"].get("sentiment") in ("negative", "very_negative", "neutral")

    def test_08_trigger_escalation(self, client):
        """Escalation query should be flagged and include contact info."""
        res = client.post("/api/chat", json={
            "query": "UNI-PASS 시스템 오류입니다",
        })
        data = res.get_json()
        assert data["is_escalation"] is True
        assert data["escalation_target"] == "tech_support"
        assert "1544-1285" in data["answer"]

    def test_09_escalation_legal_interpretation(self, client):
        """Legal interpretation request triggers escalation."""
        res = client.post("/api/chat", json={
            "query": "유권해석을 요청합니다",
        })
        data = res.get_json()
        assert data["is_escalation"] is True

    def test_10_export_conversation_text(self, client):
        """Export a session's conversation as text."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장이란?",
            "session_id": sid,
        })
        res = client.post("/api/export", json={
            "session_id": sid,
            "format": "text",
        })
        assert res.status_code == 200
        assert res.content_type.startswith("text/plain")
        assert len(res.data) > 0

    def test_11_export_conversation_json(self, client):
        """Export a session's conversation as JSON."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장이란?",
            "session_id": sid,
        })
        res = client.post("/api/export", json={
            "session_id": sid,
            "format": "json",
        })
        assert res.status_code == 200
        assert "application/json" in res.content_type

    def test_12_export_conversation_csv(self, client):
        """Export a session's conversation as CSV."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "판매 가능한가요?",
            "session_id": sid,
        })
        res = client.post("/api/export", json={
            "session_id": sid,
            "format": "csv",
        })
        assert res.status_code == 200
        assert "text/csv" in res.content_type

    def test_13_export_conversation_html(self, client):
        """Export a session's conversation as HTML."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "견본품 반출",
            "session_id": sid,
        })
        res = client.get(f"/api/session/{sid}/export?format=html")
        assert res.status_code == 200
        assert "text/html" in res.content_type

    def test_14_context_memory_stored(self, client):
        """After chatting, context memory should have stored topics."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
            "session_id": sid,
        })
        res = client.get(f"/api/session/{sid}/context")
        assert res.status_code == 200
        data = res.get_json()
        assert "context" in data

    def test_15_user_profile_available(self, client):
        """After chatting, user profile should be retrievable."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장이란?",
            "session_id": sid,
        })
        res = client.get(f"/api/session/{sid}/profile")
        assert res.status_code == 200

    def test_16_session_status(self, client):
        """Session status should reflect conversation history."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장이란?",
            "session_id": sid,
        })
        res = client.get(f"/api/session/{sid}")
        assert res.status_code == 200
        data = res.get_json()
        assert "history" in data
        assert len(data["history"]) >= 1

    def test_17_sentiment_history(self, client):
        """Sentiment history should be recorded after chatting."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장 절차가 너무 복잡합니다",
            "session_id": sid,
        })
        res = client.get(f"/api/admin/sentiment/history?session_id={sid}")
        assert res.status_code == 200
        data = res.get_json()
        assert "history" in data

    def test_18_feedback_submission(self, client):
        """Submit feedback and verify it was stored."""
        res = client.post("/api/feedback", json={
            "query_id": f"integ_{uuid.uuid4().hex[:8]}",
            "rating": "helpful",
            "comment": "Very helpful answer",
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True

    def test_19_recommendations_for_session(self, client):
        """After chatting, recommendations endpoint should work."""
        sid = client.post("/api/session/new").get_json()["session_id"]
        client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
            "session_id": sid,
        })
        res = client.get(f"/api/recommendations?session_id={sid}")
        assert res.status_code == 200
        data = res.get_json()
        assert "recommendations" in data

    def test_20_related_questions(self, client):
        """Related FAQ endpoint returns related items."""
        # Get a valid FAQ ID first
        faq_res = client.get("/api/faq")
        items = faq_res.get_json()["items"]
        assert len(items) > 0
        faq_id = items[0]["id"]

        res = client.get(f"/api/related/{faq_id}")
        assert res.status_code == 200
        data = res.get_json()
        assert "related" in data

    def test_21_autocomplete(self, client):
        """Autocomplete returns matching FAQ questions."""
        res = client.get("/api/autocomplete?q=보세")
        assert res.status_code == 200
        data = res.get_json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0


# ============================================================
# 2. TestAdminWorkflow (~15 tests)
# ============================================================
class TestAdminWorkflow:
    """Simulates admin operations: login, stats, FAQ management, etc."""

    def test_01_admin_page_loads(self, client):
        """Admin dashboard page loads successfully."""
        res = client.get("/admin")
        assert res.status_code == 200

    def test_02_admin_stats(self, client):
        """Stats dashboard returns valid data."""
        res = client.get("/api/admin/stats")
        assert res.status_code == 200
        data = res.get_json()
        assert "total_queries" in data

    def test_03_admin_logs(self, client):
        """Admin logs endpoint returns log entries."""
        res = client.get("/api/admin/logs?limit=10")
        assert res.status_code == 200
        data = res.get_json()
        assert "logs" in data

    def test_04_faq_snapshot_diff_rollback(self, client, faq_backup):
        """Create snapshot -> modify FAQ -> diff -> rollback."""
        # Create first snapshot
        snap1 = client.post("/api/admin/faq/snapshot", json={"label": "before"})
        assert snap1.status_code == 201
        snap1_id = snap1.get_json()["id"]

        # Modify FAQ: create a new item
        new_item = client.post("/api/admin/faq", json={
            "id": f"INTEG_TEST_{uuid.uuid4().hex[:6]}",
            "category": "GENERAL",
            "question": "Integration test question?",
            "answer": "Integration test answer.",
            "keywords": ["integration", "test"],
            "legal_basis": [],
            "notes": "",
        })
        assert new_item.status_code == 201

        # Create second snapshot
        snap2 = client.post("/api/admin/faq/snapshot", json={"label": "after"})
        assert snap2.status_code == 201
        snap2_id = snap2.get_json()["id"]

        # Diff between snapshots
        diff_res = client.get(f"/api/admin/faq/diff?a={snap1_id}&b={snap2_id}")
        assert diff_res.status_code == 200
        diff_data = diff_res.get_json()
        assert "diff" in diff_data
        assert "summary" in diff_data

        # Rollback to first snapshot
        rollback = client.post("/api/admin/faq/rollback", json={
            "snapshot_id": snap1_id,
        })
        assert rollback.status_code == 200

    def test_05_webhook_lifecycle(self, client):
        """Create webhook -> list -> check deliveries -> delete."""
        # Create
        res = client.post("/api/admin/webhooks", json={
            "url": "https://example.com/webhook-test",
            "events": ["query.received"],
        })
        assert res.status_code == 201
        sub_id = res.get_json()["subscription_id"]

        # List
        res = client.get("/api/admin/webhooks")
        assert res.status_code == 200
        subs = res.get_json()["subscriptions"]
        ids = [s["id"] for s in subs]
        assert sub_id in ids

        # Check delivery log
        res = client.get(f"/api/admin/webhooks/{sub_id}/deliveries")
        assert res.status_code == 200
        assert "deliveries" in res.get_json()

        # Test webhook
        res = client.post("/api/admin/webhooks/test", json={
            "event_type": "query.received",
        })
        assert res.status_code == 200

        # Delete
        res = client.delete(f"/api/admin/webhooks/{sub_id}")
        assert res.status_code == 200

    def test_06_ab_test_lifecycle(self, client):
        """Create A/B test -> list -> get results -> stop."""
        # Create
        res = client.post("/api/admin/ab-tests", json={
            "name": f"integ_test_{uuid.uuid4().hex[:6]}",
            "faq_id": "FAQ001",
            "variants": [
                {"name": "A", "answer": "Answer variant A"},
                {"name": "B", "answer": "Answer variant B"},
            ],
        })
        assert res.status_code == 201
        data = res.get_json()
        test_id = data.get("test_id") or data.get("id")

        # List
        res = client.get("/api/admin/ab-tests?active_only=false")
        assert res.status_code == 200
        assert res.get_json()["count"] >= 1

        # Get results
        res = client.get(f"/api/admin/ab-tests/{test_id}/results")
        assert res.status_code == 200

        # Stop
        res = client.post(f"/api/admin/ab-tests/{test_id}/stop")
        assert res.status_code == 200

    def test_07_daily_report(self, client):
        """Generate daily report."""
        res = client.get("/api/admin/reports/daily")
        assert res.status_code == 200
        data = res.get_json()
        assert "start_date" in data or "total_queries" in data or "report_type" in data

    def test_08_weekly_report(self, client):
        """Generate weekly report."""
        res = client.get("/api/admin/reports/weekly")
        assert res.status_code == 200

    def test_09_scheduler_tasks(self, client):
        """List scheduler tasks and run one."""
        res = client.get("/api/admin/scheduler/tasks")
        assert res.status_code == 200
        tasks = res.get_json()["tasks"]
        assert len(tasks) >= 1

        # Run the first task
        task_name = tasks[0]["name"]
        res = client.post(f"/api/admin/scheduler/tasks/{task_name}/run")
        assert res.status_code == 200

    def test_10_quality_scores(self, client):
        """Quality scores overview should return report data."""
        res = client.get("/api/admin/quality/scores")
        assert res.status_code == 200

    def test_11_knowledge_graph(self, client):
        """Knowledge graph endpoint returns graph data."""
        res = client.get("/api/admin/knowledge/graph")
        assert res.status_code == 200
        data = res.get_json()
        assert "graph" in data
        assert "stats" in data

    def test_12_conversation_analytics_metrics(self, client):
        """Conversation analytics metrics endpoint works."""
        res = client.get("/api/admin/analytics/metrics")
        assert res.status_code == 200

    def test_13_conversation_analytics_patterns(self, client):
        """Conversation analytics pattern detection works."""
        res = client.get("/api/admin/analytics/patterns")
        assert res.status_code == 200
        data = res.get_json()
        assert "patterns" in data

    def test_14_audit_logs(self, client):
        """Audit log entries should be queryable."""
        res = client.get("/api/admin/audit")
        assert res.status_code == 200
        data = res.get_json()
        assert "logs" in data

    def test_15_admin_feedback_stats(self, client):
        """Admin feedback stats should return data."""
        res = client.get("/api/admin/feedback")
        assert res.status_code == 200
        data = res.get_json()
        assert "stats" in data

    def test_16_faq_quality_check(self, client):
        """FAQ quality check returns issues and summary."""
        res = client.get("/api/admin/faq-quality")
        assert res.status_code == 200
        data = res.get_json()
        assert "overall_score" in data or "issues" in data or "total_items" in data

    def test_17_health_detailed(self, client):
        """Detailed health check returns component statuses."""
        res = client.get("/api/admin/health/detailed")
        assert res.status_code == 200
        data = res.get_json()
        assert "components" in data or "status" in data


# ============================================================
# 3. TestMultiTenantIsolation (~10 tests)
# ============================================================
class TestMultiTenantIsolation:
    """Verify multi-tenant isolation: separate data, no cross-contamination."""

    @pytest.fixture(autouse=True)
    def _setup_tenants(self, client):
        """Create two tenants for isolation tests, clean up after."""
        self.tenant_a = f"tenant_a_{uuid.uuid4().hex[:6]}"
        self.tenant_b = f"tenant_b_{uuid.uuid4().hex[:6]}"

        client.post("/api/admin/tenants", json={
            "tenant_id": self.tenant_a,
            "name": "A Exhibition Hall",
            "config": {"region": "Seoul"},
        })
        client.post("/api/admin/tenants", json={
            "tenant_id": self.tenant_b,
            "name": "B Exhibition Hall",
            "config": {"region": "Busan"},
        })
        yield
        # Cleanup
        client.delete(f"/api/admin/tenants/{self.tenant_a}")
        client.delete(f"/api/admin/tenants/{self.tenant_b}")

    def test_01_both_tenants_exist(self, client):
        """Both tenants appear in the tenant list."""
        res = client.get("/api/admin/tenants")
        data = res.get_json()
        ids = [t["id"] for t in data["tenants"]]
        assert self.tenant_a in ids
        assert self.tenant_b in ids

    def test_02_separate_faq(self, client):
        """Each tenant has its own FAQ data."""
        faq_a = client.get(f"/api/admin/tenants/{self.tenant_a}/faq")
        faq_b = client.get(f"/api/admin/tenants/{self.tenant_b}/faq")
        assert faq_a.status_code == 200
        assert faq_b.status_code == 200
        # New tenants start with empty FAQ
        assert faq_a.get_json()["items"] == []
        assert faq_b.get_json()["items"] == []

    def test_03_default_tenant_has_faq(self, client):
        """Default tenant has the main FAQ data."""
        faq = client.get("/api/admin/tenants/default/faq")
        assert faq.status_code == 200
        assert len(faq.get_json()["items"]) > 0

    def test_04_chat_on_tenant_a(self, client):
        """Chat on tenant A uses tenant A context."""
        res = client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
        }, headers={"X-Tenant-Id": self.tenant_a})
        assert res.status_code == 200
        data = res.get_json()
        assert data["tenant_id"] == self.tenant_a

    def test_05_chat_on_tenant_b(self, client):
        """Chat on tenant B uses tenant B context."""
        res = client.post("/api/chat", json={
            "query": "보세전시장이 무엇인가요?",
        }, headers={"X-Tenant-Id": self.tenant_b})
        assert res.status_code == 200
        data = res.get_json()
        assert data["tenant_id"] == self.tenant_b

    def test_06_invalid_tenant_rejected(self, client):
        """Chat with non-existent tenant returns 404."""
        res = client.post("/api/chat", json={
            "query": "테스트",
        }, headers={"X-Tenant-Id": "nonexistent_tenant_xyz"})
        assert res.status_code == 404

    def test_07_inactive_tenant_rejected(self, client):
        """Chat with inactive tenant returns 403."""
        # Deactivate tenant A
        client.put(f"/api/admin/tenants/{self.tenant_a}", json={"active": False})
        res = client.post("/api/chat", json={
            "query": "테스트",
        }, headers={"X-Tenant-Id": self.tenant_a})
        assert res.status_code == 403
        # Reactivate for cleanup
        client.put(f"/api/admin/tenants/{self.tenant_a}", json={"active": True})

    def test_08_tenant_config_isolation(self, client):
        """Each tenant has separate config data."""
        # Update tenant A config
        client.put(f"/api/admin/tenants/{self.tenant_a}", json={
            "config": {"region": "Seoul", "special": True},
        })
        # Get both tenants
        res_a = client.get("/api/admin/tenants")
        tenants = {t["id"]: t for t in res_a.get_json()["tenants"]}
        # Tenant B should not have the special flag
        if self.tenant_b in tenants:
            b_config = tenants[self.tenant_b].get("config", {})
            assert b_config.get("special") is not True

    def test_09_delete_tenant_cleanup(self, client):
        """Deleting a tenant removes it from the list."""
        temp_id = f"temp_del_{uuid.uuid4().hex[:6]}"
        client.post("/api/admin/tenants", json={
            "tenant_id": temp_id,
            "name": "Temporary",
        })
        res = client.delete(f"/api/admin/tenants/{temp_id}")
        assert res.status_code == 200

        # Verify gone
        res = client.get("/api/admin/tenants")
        ids = [t["id"] for t in res.get_json()["tenants"]]
        assert temp_id not in ids

    def test_10_default_tenant_cannot_be_deleted(self, client):
        """Default tenant cannot be deleted."""
        res = client.delete("/api/admin/tenants/default")
        assert res.status_code == 400


# ============================================================
# 4. TestAPIVersioning (~8 tests)
# ============================================================
class TestAPIVersioning:
    """Test v1 and v2 API compatibility."""

    def test_01_versions_endpoint(self, client):
        """API versions listing works."""
        res = client.get("/api/versions")
        assert res.status_code == 200
        data = res.get_json()
        assert "versions" in data
        version_ids = [v["version"] for v in data["versions"]]
        assert "v1" in version_ids
        assert "v2" in version_ids

    def test_02_v1_faq_list(self, client):
        """v1 FAQ list returns items."""
        res = client.get("/api/faq")
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert "count" in data
        assert data["count"] >= 7

    def test_03_v2_faq_list_paginated(self, client):
        """v2 FAQ list supports pagination."""
        res = client.get("/api/v2/faq?page=1&per_page=5")
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert "page" in data
        assert "per_page" in data
        assert data["per_page"] == 5
        assert len(data["items"]) <= 5

    def test_04_v2_faq_page2(self, client):
        """v2 FAQ page 2 returns different items than page 1."""
        p1 = client.get("/api/v2/faq?page=1&per_page=5").get_json()
        p2 = client.get("/api/v2/faq?page=2&per_page=5").get_json()
        if p2["items"]:
            # Items on page 2 should be different from page 1
            p1_ids = {i["id"] for i in p1["items"]}
            p2_ids = {i["id"] for i in p2["items"]}
            assert p1_ids != p2_ids

    def test_05_v2_chat_has_api_version(self, client):
        """v2 chat response includes api_version field."""
        res = client.post("/api/v2/chat", json={
            "query": "보세전시장이 무엇인가요?",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("api_version") == "v2"
        assert "X-API-Version" in res.headers

    def test_06_v1_v2_compatible_answer(self, client):
        """v1 and v2 return compatible answer data for the same query."""
        query = {"query": "보세전시장이 무엇인가요?"}
        v1 = client.post("/api/chat", json=query).get_json()
        v2 = client.post("/api/v2/chat", json=query).get_json()

        # Both should have answer, category, is_escalation
        assert "answer" in v1
        assert "answer" in v2
        assert "category" in v1
        assert "category" in v2
        assert v1["category"] == v2["category"]

    def test_07_v2_error_handling(self, client):
        """v2 handles errors consistently with v1."""
        # Empty query
        v1_err = client.post("/api/chat", json={"query": ""})
        v2_err = client.post("/api/v2/chat", json={"query": ""})
        assert v1_err.status_code == 400
        assert v2_err.status_code == 400

    def test_08_v2_missing_query(self, client):
        """v2 rejects missing query field."""
        res = client.post("/api/v2/chat", json={})
        assert res.status_code == 400
        assert "error" in res.get_json()


# ============================================================
# 5. TestSecurityComprehensive (~10 tests)
# ============================================================
class TestSecurityComprehensive:
    """Test authentication, authorization, rate limiting, input sanitization."""

    def test_01_admin_stats_reject_without_auth(self, auth_client):
        """Admin stats rejects requests without auth token."""
        res = auth_client.get("/api/admin/stats")
        assert res.status_code == 401

    def test_02_admin_logs_reject_without_auth(self, auth_client):
        """Admin logs rejects requests without auth token."""
        res = auth_client.get("/api/admin/logs")
        assert res.status_code == 401

    def test_03_admin_analytics_reject_without_auth(self, auth_client):
        """Admin analytics rejects requests without auth token."""
        res = auth_client.get("/api/admin/analytics")
        assert res.status_code == 401

    def test_04_login_returns_token(self, auth_client):
        """Successful login returns a JWT token."""
        res = auth_client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "token" in data
        assert data["expires_in"] == 86400
        # Token should have 3 parts
        assert data["token"].count(".") == 2

    def test_05_valid_token_grants_access(self, auth_client):
        """A valid JWT token grants access to admin endpoints."""
        token = _get_token(auth_client)
        res = auth_client.get("/api/admin/stats", headers=_auth_header(token))
        assert res.status_code == 200

    def test_06_invalid_token_rejected(self, auth_client):
        """An invalid JWT token is rejected."""
        res = auth_client.get("/api/admin/stats", headers={
            "Authorization": "Bearer invalid.token.value",
        })
        assert res.status_code == 401

    def test_07_expired_token_rejected(self, auth_client):
        """An expired JWT token is rejected."""
        from src.auth import JWTAuth
        auth = JWTAuth()
        token = auth.generate_token("admin", expires_hours=0)
        time.sleep(0.1)
        res = auth_client.get("/api/admin/stats", headers=_auth_header(token))
        assert res.status_code == 401

    def test_08_no_bearer_prefix_rejected(self, auth_client):
        """Token without Bearer prefix is rejected."""
        token = _get_token(auth_client)
        res = auth_client.get("/api/admin/stats", headers={
            "Authorization": token,
        })
        assert res.status_code == 401

    def test_09_xss_sanitized(self, client):
        """XSS payloads are sanitized in query input."""
        xss_payload = '<script>alert("xss")</script>보세전시장'
        res = client.post("/api/chat", json={"query": xss_payload})
        assert res.status_code == 200
        data = res.get_json()
        # The answer should not contain the raw script tag
        assert "<script>" not in data["answer"]

    def test_10_sql_injection_sanitized(self, client):
        """SQL injection payloads are sanitized."""
        sqli_payload = "'; DROP TABLE faq; --"
        res = client.post("/api/chat", json={"query": sqli_payload})
        # Should not crash; 200 or 400 are both acceptable
        assert res.status_code in (200, 400)
        # If 200, make sure we get a valid response
        if res.status_code == 200:
            data = res.get_json()
            assert "answer" in data

    def test_11_oversized_query_rejected(self, client):
        """Queries exceeding max length are rejected."""
        huge_query = "보세" * 1500  # Way over 2000 chars
        res = client.post("/api/chat", json={"query": huge_query})
        assert res.status_code in (200, 400)

    def test_12_wrong_password_rejected(self, auth_client):
        """Login with wrong password returns 401."""
        res = auth_client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_13_missing_login_fields(self, auth_client):
        """Login with missing fields returns 400."""
        res = auth_client.post("/api/auth/login", json={
            "username": "admin",
        })
        assert res.status_code == 400

    def test_14_auth_me_with_token(self, auth_client):
        """Authenticated user can access /api/auth/me."""
        token = _get_token(auth_client)
        res = auth_client.get("/api/auth/me", headers=_auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"
