"""Tests for Track SS — per-tenant rate-limit override."""
import json
import os
import pytest
from src.tenant_rate_limit import GLOBAL_DEFAULT, RateLimit, TenantConfigCache, resolve_rate_limit


@pytest.fixture
def tenants_dir(tmp_path):
    base = tmp_path / "tenants"
    (base / "acme").mkdir(parents=True)
    (base / "globex").mkdir(parents=True)
    (base / "acme" / "config.json").write_text(json.dumps({
        "rate_limit": {
            "default": {"per_minute": 200, "per_hour": 8000},
            "/api/chat": {"per_minute": 100, "per_hour": 3000},
            "/api/admin/*": {"per_minute": 30, "per_hour": 600},
        }
    }), encoding="utf-8")
    (base / "globex" / "config.json").write_text(json.dumps({
        "rate_limit": {"default": {"per_minute": 5, "per_hour": 100}}
    }), encoding="utf-8")
    return str(base)


def test_no_tenant_default(tenants_dir):
    assert resolve_rate_limit(None, "/api/chat", cache=TenantConfigCache(tenants_dir)) == GLOBAL_DEFAULT


def test_tenant_route_override(tenants_dir):
    assert resolve_rate_limit("acme", "/api/chat", cache=TenantConfigCache(tenants_dir)) == RateLimit(100, 3000)


def test_wildcard(tenants_dir):
    assert resolve_rate_limit("acme", "/api/admin/users", cache=TenantConfigCache(tenants_dir)) == RateLimit(30, 600)


def test_fallback_chain(tenants_dir):
    cache = TenantConfigCache(tenants_dir)
    assert resolve_rate_limit("acme", "/api/health", cache=cache) == RateLimit(200, 8000)
    assert resolve_rate_limit("globex", "/api/x", cache=cache) == RateLimit(5, 100)
    assert resolve_rate_limit("unknown", "/api/chat", cache=cache) == GLOBAL_DEFAULT


def test_invalidate(tenants_dir):
    cache = TenantConfigCache(tenants_dir, ttl_seconds=999.0)
    first = resolve_rate_limit("acme", "/api/chat", cache=cache)
    p = os.path.join(tenants_dir, "acme", "config.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"rate_limit": {"/api/chat": {"per_minute": 7, "per_hour": 70}}}, f)
    assert resolve_rate_limit("acme", "/api/chat", cache=cache) == first  # cached
    cache.invalidate("acme")
    assert resolve_rate_limit("acme", "/api/chat", cache=cache) == RateLimit(7, 70)


def test_bad_config(tmp_path):
    base = tmp_path / "tenants"
    (base / "broken").mkdir(parents=True)
    (base / "broken" / "config.json").write_text("not json", encoding="utf-8")
    assert resolve_rate_limit("broken", "/api/chat", cache=TenantConfigCache(str(base))) == GLOBAL_DEFAULT
