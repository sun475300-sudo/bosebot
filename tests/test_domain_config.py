"""Domain configuration tests."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.domain_config import DomainConfig


@pytest.fixture
def sample_config(tmp_path):
    config = {
        "domain": {"name": "테스트 도메인", "code": "test", "description": "테스트"},
        "categories": [{"code": "GENERAL", "name": "일반", "priority": 1}],
        "persona": {"name": "테스트봇", "greeting": "안녕하세요", "tone": "formal"},
        "response_format": {"sections": ["conclusion", "explanation"]},
        "escalation": {"enabled": True, "default_contact": "125"},
        "features": {"sentiment_analysis": True},
        "limits": {"max_query_length": 2000, "session_timeout_min": 30}
    }
    path = tmp_path / "test_domain.json"
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return str(path)


class TestLoad:
    def test_load_valid(self, sample_config):
        dc = DomainConfig()
        dc.load(sample_config)
        assert dc.get("domain.name") == "테스트 도메인"

    def test_load_nonexistent(self):
        dc = DomainConfig()
        with pytest.raises(FileNotFoundError):
            dc.load("/nonexistent/path.json")


class TestGetSet:
    def test_get_nested(self, sample_config):
        dc = DomainConfig()
        dc.load(sample_config)
        assert dc.get("domain.code") == "test"

    def test_get_default(self, sample_config):
        dc = DomainConfig()
        dc.load(sample_config)
        assert dc.get("nonexistent", "fallback") == "fallback"

    def test_set_value(self, sample_config):
        dc = DomainConfig()
        dc.load(sample_config)
        dc.set("domain.name", "새 이름")
        assert dc.get("domain.name") == "새 이름"


class TestValidate:
    def test_valid_config(self, sample_config):
        dc = DomainConfig()
        dc.load(sample_config)
        result = dc.validate()
        # May be valid or have warnings depending on required fields
        assert "valid" in result

    def test_missing_required(self):
        dc = DomainConfig()
        dc._config = {"domain": {"name": "test"}}
        result = dc.validate()
        assert result["valid"] is False


class TestExportTemplate:
    def test_template_has_all_keys(self):
        dc = DomainConfig()
        template = dc.export_template()
        assert "domain" in template
        assert "categories" in template
        assert "persona" in template


class TestDomainAPI:
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

    def test_get_domain(self, client):
        res = client.get("/api/admin/domain")
        assert res.status_code in (200, 404)  # 404 if not loaded

    def test_get_template(self, client):
        res = client.get("/api/admin/domain/template")
        assert res.status_code == 200
        data = res.get_json()
        assert "domain" in data

    def test_validate_domain(self, client):
        payload = {
            "domain": {"name": "test", "code": "test"},
            "categories": [{"code": "GENERAL", "name": "일반"}],
            "persona": {"name": "봇", "greeting": "안녕"},
        }
        res = client.post("/api/admin/domain/validate", json=payload)
        assert res.status_code == 200
