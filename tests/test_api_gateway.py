"""Tests for API gateway versioning, pagination, sorting, and v2 endpoints."""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api_gateway import APIGateway, PaginationHelper, SortHelper
from web_server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── APIGateway tests ──────────────────────────────────────────────────────


class TestAPIGateway:
    def test_register_version(self):
        gw = APIGateway()
        gw.register_version("v1")
        versions = gw.get_active_versions()
        assert len(versions) == 1
        assert versions[0]["version"] == "v1"
        assert versions[0]["status"] == "active"

    def test_register_multiple_versions(self):
        gw = APIGateway()
        gw.register_version("v1")
        gw.register_version("v2", status="active")
        gw.register_version("v3", status="beta")
        versions = gw.get_active_versions()
        assert len(versions) == 3
        statuses = {v["version"]: v["status"] for v in versions}
        assert statuses["v1"] == "active"
        assert statuses["v3"] == "beta"

    def test_deprecate_version(self):
        gw = APIGateway()
        gw.register_version("v1")
        gw.deprecate_version("v1", "2026-12-31")
        assert gw.is_deprecated("v1") is True

    def test_deprecate_unregistered_version_raises(self):
        gw = APIGateway()
        with pytest.raises(ValueError):
            gw.deprecate_version("v99", "2026-12-31")

    def test_is_deprecated_false_for_active(self):
        gw = APIGateway()
        gw.register_version("v1")
        assert gw.is_deprecated("v1") is False

    def test_is_deprecated_false_for_unknown(self):
        gw = APIGateway()
        assert gw.is_deprecated("v99") is False

    def test_deprecation_headers_added(self):
        gw = APIGateway()
        gw.register_version("v1")
        gw.deprecate_version("v1", "2026-12-31")

        with app.test_request_context():
            from flask import jsonify as _jsonify
            resp = _jsonify({"ok": True})
            resp = gw.add_deprecation_headers(resp, "v1")
            assert resp.headers.get("Sunset") == "2026-12-31"
            assert resp.headers.get("Deprecation") == "true"

    def test_deprecation_headers_not_added_for_active(self):
        gw = APIGateway()
        gw.register_version("v1")

        with app.test_request_context():
            from flask import jsonify as _jsonify
            resp = _jsonify({"ok": True})
            resp = gw.add_deprecation_headers(resp, "v1")
            assert "Sunset" not in resp.headers
            assert "Deprecation" not in resp.headers

    def test_get_active_versions_shows_deprecated_status(self):
        gw = APIGateway()
        gw.register_version("v1")
        gw.register_version("v2")
        gw.deprecate_version("v1", "2026-06-01")
        versions = gw.get_active_versions()
        statuses = {v["version"]: v["status"] for v in versions}
        assert statuses["v1"] == "deprecated"
        assert statuses["v2"] == "active"


# ── PaginationHelper tests ───────────────────────────────────────────────


class TestPaginationHelper:
    def test_basic_pagination(self):
        items = list(range(50))
        result = PaginationHelper.paginate(items, page=1, per_page=10)
        assert result["page"] == 1
        assert result["per_page"] == 10
        assert result["total"] == 50
        assert result["pages"] == 5
        assert result["items"] == list(range(10))

    def test_second_page(self):
        items = list(range(50))
        result = PaginationHelper.paginate(items, page=2, per_page=10)
        assert result["items"] == list(range(10, 20))
        assert result["page"] == 2

    def test_last_page_partial(self):
        items = list(range(25))
        result = PaginationHelper.paginate(items, page=3, per_page=10)
        assert result["items"] == list(range(20, 25))
        assert result["pages"] == 3

    def test_page_beyond_total(self):
        items = list(range(10))
        result = PaginationHelper.paginate(items, page=5, per_page=10)
        assert result["items"] == []
        assert result["total"] == 10

    def test_empty_items(self):
        result = PaginationHelper.paginate([], page=1, per_page=10)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["pages"] == 1

    def test_page_zero_treated_as_one(self):
        items = list(range(10))
        result = PaginationHelper.paginate(items, page=0, per_page=5)
        assert result["page"] == 1
        assert result["items"] == list(range(5))

    def test_per_page_zero_treated_as_one(self):
        items = list(range(5))
        result = PaginationHelper.paginate(items, page=1, per_page=0)
        assert result["per_page"] == 1
        assert len(result["items"]) == 1

    def test_default_per_page(self):
        items = list(range(50))
        result = PaginationHelper.paginate(items)
        assert result["per_page"] == 20
        assert len(result["items"]) == 20

    def test_single_item(self):
        result = PaginationHelper.paginate(["only"], page=1, per_page=10)
        assert result["items"] == ["only"]
        assert result["total"] == 1
        assert result["pages"] == 1


# ── SortHelper tests ─────────────────────────────────────────────────────


class TestSortHelper:
    def test_sort_ascending(self):
        items = [{"name": "b"}, {"name": "a"}, {"name": "c"}]
        result = SortHelper.sort_items(items, "name", "asc")
        assert [i["name"] for i in result] == ["a", "b", "c"]

    def test_sort_descending(self):
        items = [{"name": "b"}, {"name": "a"}, {"name": "c"}]
        result = SortHelper.sort_items(items, "name", "desc")
        assert [i["name"] for i in result] == ["c", "b", "a"]

    def test_sort_by_numeric_field(self):
        items = [{"id": 3}, {"id": 1}, {"id": 2}]
        result = SortHelper.sort_items(items, "id", "asc")
        assert [i["id"] for i in result] == [1, 2, 3]

    def test_sort_missing_key_uses_empty_string(self):
        items = [{"name": "b"}, {"other": "x"}, {"name": "a"}]
        result = SortHelper.sort_items(items, "name", "asc")
        # Item without 'name' key uses "" which sorts first
        assert result[0] == {"other": "x"}

    def test_sort_does_not_mutate_original(self):
        items = [{"id": 3}, {"id": 1}, {"id": 2}]
        original = list(items)
        SortHelper.sort_items(items, "id", "asc")
        assert items == original

    def test_sort_empty_list(self):
        result = SortHelper.sort_items([], "name", "asc")
        assert result == []


# ── v2 FAQ endpoint tests ────────────────────────────────────────────────


class TestV2FaqEndpoint:
    def test_v2_faq_returns_paginated(self, client):
        res = client.get("/api/v2/faq?page=1&per_page=3")
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert "page" in data
        assert "per_page" in data
        assert "total" in data
        assert "pages" in data
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["items"]) <= 3

    def test_v2_faq_has_version_header(self, client):
        res = client.get("/api/v2/faq")
        assert res.headers.get("X-API-Version") == "v2"

    def test_v2_faq_default_pagination(self, client):
        res = client.get("/api/v2/faq")
        data = res.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 20

    def test_v2_faq_sort_descending(self, client):
        res = client.get("/api/v2/faq?sort=id&order=desc&per_page=100")
        data = res.get_json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids, reverse=True)

    def test_v2_faq_sort_ascending(self, client):
        res = client.get("/api/v2/faq?sort=id&order=asc&per_page=100")
        data = res.get_json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)

    def test_v2_faq_page_2(self, client):
        res1 = client.get("/api/v2/faq?page=1&per_page=2")
        res2 = client.get("/api/v2/faq?page=2&per_page=2")
        data1 = res1.get_json()
        data2 = res2.get_json()
        # Pages should return different items
        if data1["total"] > 2:
            assert data1["items"] != data2["items"]

    def test_v2_faq_item_structure(self, client):
        res = client.get("/api/v2/faq?per_page=1")
        data = res.get_json()
        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "category" in item
            assert "question" in item


# ── /api/versions endpoint tests ─────────────────────────────────────────


class TestVersionsEndpoint:
    def test_versions_returns_list(self, client):
        res = client.get("/api/versions")
        assert res.status_code == 200
        data = res.get_json()
        assert "versions" in data
        assert isinstance(data["versions"], list)

    def test_versions_contains_v1_and_v2(self, client):
        res = client.get("/api/versions")
        data = res.get_json()
        version_names = [v["version"] for v in data["versions"]]
        assert "v1" in version_names
        assert "v2" in version_names

    def test_versions_have_status(self, client):
        res = client.get("/api/versions")
        data = res.get_json()
        for v in data["versions"]:
            assert "status" in v
            assert "version" in v


# ── v2 chat endpoint tests ───────────────────────────────────────────────


class TestV2ChatEndpoint:
    def test_v2_chat_includes_api_version(self, client):
        res = client.post(
            "/api/v2/chat",
            json={"query": "보세전시장이란 무엇인가요?"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["api_version"] == "v2"

    def test_v2_chat_has_version_header(self, client):
        res = client.post(
            "/api/v2/chat",
            json={"query": "보세전시장이란 무엇인가요?"},
        )
        assert res.headers.get("X-API-Version") == "v2"

    def test_v2_chat_missing_query(self, client):
        res = client.post("/api/v2/chat", json={})
        assert res.status_code == 400

    def test_v2_chat_returns_answer(self, client):
        res = client.post(
            "/api/v2/chat",
            json={"query": "보세전시장이란 무엇인가요?"},
        )
        data = res.get_json()
        assert "answer" in data
        assert "category" in data


# ── Deprecation header integration tests ─────────────────────────────────


class TestDeprecationHeaders:
    def test_active_version_no_deprecation_header(self, client):
        res = client.get("/api/v2/faq")
        assert "Deprecation" not in res.headers
        assert "Sunset" not in res.headers

    def test_deprecation_headers_on_gateway_object(self):
        gw = APIGateway()
        gw.register_version("v1")
        gw.deprecate_version("v1", "2026-06-30")

        with app.test_request_context():
            from flask import jsonify as _jsonify
            resp = _jsonify({})
            resp = gw.add_deprecation_headers(resp, "v1")
            assert resp.headers["Sunset"] == "2026-06-30"
            assert resp.headers["Deprecation"] == "true"

        # Non-deprecated version should not get headers
        gw.register_version("v2")
        with app.test_request_context():
            resp2 = _jsonify({})
            resp2 = gw.add_deprecation_headers(resp2, "v2")
            assert "Sunset" not in resp2.headers
