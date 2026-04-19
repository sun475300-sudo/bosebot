"""국가법령정보센터 API 동기화 테스트."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.law_api_sync import LawSyncManager, LawAPIClient, MONITORED_LAWS


@pytest.fixture
def sync_manager(tmp_path):
    client = LawAPIClient(oc="")
    return LawSyncManager(api_client=client, db_path=str(tmp_path / "sync.db"))


class TestLawSyncManager:
    def test_init_creates_tables(self, sync_manager):
        history = sync_manager.get_sync_history()
        assert isinstance(history, list)

    def test_record_check_new(self, sync_manager):
        changed = sync_manager._record_check("관세법", "제190조", "테스트 내용")
        assert changed is False  # first time = no previous to compare

    def test_record_check_unchanged(self, sync_manager):
        sync_manager._record_check("관세법", "제190조", "테스트 내용")
        changed = sync_manager._record_check("관세법", "제190조", "테스트 내용")
        assert changed is False

    def test_record_check_changed(self, sync_manager):
        sync_manager._record_check("관세법", "제190조", "원래 내용")
        changed = sync_manager._record_check("관세법", "제190조", "변경된 내용")
        assert changed is True

    def test_get_cached_content(self, sync_manager):
        sync_manager._record_check("관세법", "제190조", "캐시 테스트")
        cached = sync_manager.get_cached_content("관세법", "제190조")
        assert cached is not None
        assert cached["content"] == "캐시 테스트"

    def test_get_cached_content_not_found(self, sync_manager):
        cached = sync_manager.get_cached_content("없는법", "제1조")
        assert cached is None

    def test_sync_history(self, sync_manager):
        sync_manager._record_check("관세법", "제190조", "내용1")
        sync_manager._record_check("관세법", "제190조", "내용2")
        history = sync_manager.get_sync_history(limit=10)
        assert len(history) == 2

    def test_monitored_laws(self, sync_manager):
        laws = sync_manager.get_monitored_laws()
        assert len(laws) >= 2
        assert laws[0]["law_name"] == "관세법"


class TestLawAPIClient:
    def test_init_default(self):
        client = LawAPIClient()
        assert client.oc == ""

    def test_init_with_oc(self):
        client = LawAPIClient(oc="test_key")
        assert client.oc == "test_key"

    def test_get_article_text_none_xml(self):
        client = LawAPIClient()
        result = client.get_article_text(None, "제190조")
        assert result is None

    def test_get_article_text_invalid_xml(self):
        client = LawAPIClient()
        result = client.get_article_text("not xml", "제190조")
        assert result is None


class TestMonitoredLaws:
    def test_has_customs_act(self):
        names = [law["law_name"] for law in MONITORED_LAWS]
        assert "관세법" in names

    def test_has_customs_decree(self):
        names = [law["law_name"] for law in MONITORED_LAWS]
        assert "관세법 시행령" in names

    def test_articles_190(self):
        for law in MONITORED_LAWS:
            if law["law_name"] == "관세법":
                assert "제190조" in law["articles"]

    def test_articles_208(self):
        for law in MONITORED_LAWS:
            if law["law_name"] == "관세법 시행령":
                assert "제208조" in law["articles"]


class TestUpdateLegalReferences:
    def test_update_with_no_cache(self, sync_manager, tmp_path):
        ref_path = tmp_path / "legal_ref.json"
        ref_path.write_text(json.dumps({
            "references": [{"law_name": "관세법", "article": "제190조", "summary": "원래"}]
        }, ensure_ascii=False), encoding="utf-8")
        import src.law_api_sync as mod
        original_path = mod.LEGAL_REF_PATH
        mod.LEGAL_REF_PATH = str(ref_path)
        try:
            result = sync_manager.update_legal_references()
            assert result["updated"] == 0
        finally:
            mod.LEGAL_REF_PATH = original_path

    def test_update_with_cached_change(self, sync_manager, tmp_path):
        sync_manager._record_check("관세법", "제190조", "새로운 법령 내용입니다. 보세전시장은 박람회 등의 운영을 위해...")
        ref_path = tmp_path / "legal_ref.json"
        ref_path.write_text(json.dumps({
            "references": [{"law_name": "관세법", "article": "제190조", "summary": "원래 내용"}]
        }, ensure_ascii=False), encoding="utf-8")
        import src.law_api_sync as mod
        original_path = mod.LEGAL_REF_PATH
        mod.LEGAL_REF_PATH = str(ref_path)
        try:
            result = sync_manager.update_legal_references()
            assert result["updated"] == 1
        finally:
            mod.LEGAL_REF_PATH = original_path


class TestLawSyncAPI:
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

    def test_history_endpoint(self, client):
        res = client.get("/api/admin/law-sync/history")
        assert res.status_code == 200
        assert "history" in res.get_json()

    def test_monitored_endpoint(self, client):
        res = client.get("/api/admin/law-sync/monitored")
        assert res.status_code == 200
        data = res.get_json()
        assert "laws" in data
        assert len(data["laws"]) >= 2
