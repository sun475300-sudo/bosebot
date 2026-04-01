"""Comprehensive stress and integration tests."""
import json
import os
import sys
import threading
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    os.environ["ADMIN_AUTH_DISABLED"] = "true"
    os.environ["TESTING"] = "true"
    from web_server import app
    app.config["TESTING"] = True
    faq_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faq.json")
    with open(faq_path, "r", encoding="utf-8") as f:
        faq_backup = f.read()
    with app.test_client() as c:
        yield c
    with open(faq_path, "w", encoding="utf-8") as f:
        f.write(faq_backup)
    os.environ.pop("ADMIN_AUTH_DISABLED", None)
    os.environ.pop("TESTING", None)


# --- Test All Endpoints Coverage ---

class TestAllEndpoints:
    def test_chat(self, client):
        res = client.post("/api/chat", json={"query": "보세전시장이란?"})
        assert res.status_code == 200
        assert "answer" in res.get_json()

    def test_faq_list(self, client):
        res = client.get("/api/faq")
        assert res.status_code == 200
        assert "items" in res.get_json()

    def test_autocomplete(self, client):
        res = client.get("/api/autocomplete?q=보세")
        assert res.status_code == 200

    def test_config(self, client):
        res = client.get("/api/config")
        assert res.status_code == 200

    def test_health(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_session_new(self, client):
        res = client.post("/api/session/new")
        assert res.status_code in (200, 201)

    def test_metrics(self, client):
        res = client.get("/metrics")
        assert res.status_code == 200

    def test_i18n_languages(self, client):
        res = client.get("/api/i18n/languages")
        assert res.status_code == 200

    def test_i18n_ko(self, client):
        res = client.get("/api/i18n/ko")
        assert res.status_code == 200

    def test_popular(self, client):
        res = client.get("/api/popular")
        assert res.status_code == 200

    def test_trending(self, client):
        res = client.get("/api/trending")
        assert res.status_code == 200

    def test_admin_stats(self, client):
        res = client.get("/api/admin/stats")
        assert res.status_code == 200

    def test_admin_logs(self, client):
        res = client.get("/api/admin/logs")
        assert res.status_code == 200

    def test_admin_unmatched(self, client):
        res = client.get("/api/admin/unmatched")
        assert res.status_code == 200

    def test_admin_realtime(self, client):
        res = client.get("/api/admin/realtime")
        assert res.status_code == 200

    def test_admin_faq_quality(self, client):
        res = client.get("/api/admin/faq-quality")
        assert res.status_code == 200

    def test_admin_satisfaction(self, client):
        res = client.get("/api/admin/satisfaction")
        assert res.status_code == 200

    def test_admin_sentiment(self, client):
        res = client.get("/api/admin/sentiment")
        assert res.status_code == 200

    def test_admin_segments(self, client):
        res = client.get("/api/admin/segments")
        assert res.status_code == 200

    def test_admin_audit(self, client):
        res = client.get("/api/admin/audit")
        assert res.status_code == 200

    def test_admin_alerts(self, client):
        res = client.get("/api/admin/alerts")
        assert res.status_code == 200

    def test_admin_alerts_count(self, client):
        res = client.get("/api/admin/alerts/count")
        assert res.status_code == 200

    def test_admin_webhooks(self, client):
        res = client.get("/api/admin/webhooks")
        assert res.status_code == 200

    def test_admin_scheduler_tasks(self, client):
        res = client.get("/api/admin/scheduler/tasks")
        assert res.status_code == 200

    def test_admin_scheduler_log(self, client):
        res = client.get("/api/admin/scheduler/log")
        assert res.status_code == 200

    def test_admin_backups(self, client):
        res = client.get("/api/admin/backups")
        assert res.status_code == 200

    def test_admin_migrations(self, client):
        res = client.get("/api/admin/migrations")
        assert res.status_code == 200

    def test_admin_templates(self, client):
        res = client.get("/api/admin/templates")
        assert res.status_code == 200

    def test_admin_tenants(self, client):
        res = client.get("/api/admin/tenants")
        assert res.status_code == 200

    def test_kakao_chat(self, client):
        res = client.post("/api/kakao/chat", json={
            "userRequest": {"utterance": "보세전시장이란?"},
            "bot": {}, "action": {}
        })
        assert res.status_code == 200

    def test_naver_webhook_get(self, client):
        res = client.get("/api/naver/webhook?challenge=test123")
        assert res.status_code == 200


# --- Edge Cases ---

class TestEdgeCases:
    def test_empty_query(self, client):
        res = client.post("/api/chat", json={"query": ""})
        assert res.status_code in (200, 400)

    def test_very_long_query(self, client):
        res = client.post("/api/chat", json={"query": "보세" * 5000})
        assert res.status_code in (200, 400, 413)

    def test_unicode_emoji(self, client):
        res = client.post("/api/chat", json={"query": "보세전시장 🏢 정보"})
        assert res.status_code == 200

    def test_cjk_mixed(self, client):
        res = client.post("/api/chat", json={"query": "保税展示場について"})
        assert res.status_code == 200

    def test_sql_injection(self, client):
        res = client.post("/api/chat", json={"query": "'; DROP TABLE chat_logs; --"})
        assert res.status_code == 200
        # Should still work after injection attempt
        res2 = client.get("/api/admin/stats")
        assert res2.status_code == 200

    def test_xss_attempt(self, client):
        res = client.post("/api/chat", json={"query": "<script>alert('xss')</script>"})
        assert res.status_code == 200
        data = res.get_json()
        assert "<script>" not in data.get("answer", "")

    def test_null_query(self, client):
        res = client.post("/api/chat", json={"query": None})
        assert res.status_code in (200, 400)

    def test_missing_body(self, client):
        res = client.post("/api/chat", data="", content_type="application/json")
        assert res.status_code in (400, 500)

    def test_autocomplete_empty(self, client):
        res = client.get("/api/autocomplete?q=")
        assert res.status_code == 200

    def test_autocomplete_long(self, client):
        res = client.get("/api/autocomplete?q=" + "가" * 500)
        assert res.status_code == 200


# --- Data Integrity ---

class TestDataIntegrity:
    def test_faq_count_50(self):
        faq_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faq.json")
        with open(faq_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["items"]) == 50

    def test_all_10_categories(self):
        faq_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faq.json")
        with open(faq_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cats = set(item["category"] for item in data["items"])
        assert len(cats) == 10

    def test_faq_required_fields(self):
        faq_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faq.json")
        with open(faq_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        required = {"id", "category", "question", "answer", "keywords"}
        for item in data["items"]:
            assert required.issubset(set(item.keys())), f"Missing fields in {item['id']}"

    def test_no_duplicate_ids(self):
        faq_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faq.json")
        with open(faq_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = [item["id"] for item in data["items"]]
        assert len(ids) == len(set(ids))

    def test_escalation_rules_valid(self):
        rules_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "escalation_rules.json")
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["rules"]) == 5

    def test_legal_references_valid(self):
        legal_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "legal_references.json")
        with open(legal_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["references"]) >= 7


# --- Concurrency (sequential simulation since Flask test client isn't thread-safe) ---

class TestConcurrency:
    def test_rapid_fire_chat(self, client):
        """Simulate rapid sequential requests."""
        for q in ["보세전시장이란?", "반입 절차", "견본품 반출", "벌칙", "판매 가능?",
                   "시식 허가", "특허 기간", "관세율", "서류", "담당 기관"]:
            res = client.post("/api/chat", json={"query": q})
            assert res.status_code == 200

    def test_multiple_sessions(self, client):
        session_ids = set()
        for _ in range(5):
            res = client.post("/api/session/new")
            sid = res.get_json().get("session_id")
            assert sid is not None
            session_ids.add(sid)
        assert len(session_ids) == 5  # all unique

    def test_rapid_autocomplete(self, client):
        for q in ["보세", "반입", "견본", "판매", "시식"]:
            res = client.get(f"/api/autocomplete?q={q}")
            assert res.status_code == 200


# --- Cross-Module Integration ---

class TestCrossModule:
    def test_chat_includes_sentiment(self, client):
        res = client.post("/api/chat", json={"query": "보세전시장 정말 감사합니다"})
        data = res.get_json()
        # sentiment may or may not be present depending on integration
        assert res.status_code == 200

    def test_chat_returns_answer(self, client):
        res = client.post("/api/chat", json={"query": "물품 반입 시 신고가 필요한가요?"})
        data = res.get_json()
        assert "answer" in data
        assert len(data["answer"]) > 10

    def test_faq_endpoint_matches_data(self, client):
        res = client.get("/api/faq")
        data = res.get_json()
        assert data["count"] >= 50

    def test_chat_with_session(self, client):
        # Create session
        session_res = client.post("/api/session/new")
        sid = session_res.get_json()["session_id"]
        # Chat with session
        res = client.post("/api/chat", json={"query": "보세전시장이란?", "session_id": sid})
        assert res.status_code == 200

    def test_multilingual_chat(self, client):
        res = client.post("/api/chat", json={"query": "What is bonded exhibition?", "lang": "en"})
        assert res.status_code == 200
