"""Track SS — per-tenant rate-limit override resolver."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimit:
    per_minute: int
    per_hour: int


GLOBAL_DEFAULT = RateLimit(per_minute=60, per_hour=1000)


@dataclass
class TenantConfigCache:
    base_dir: str
    ttl_seconds: float = 60.0
    _entries: Dict[str, tuple] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def load(self, tenant_id: str) -> dict:
        if not tenant_id:
            return {}
        path = os.path.join(self.base_dir, tenant_id, "config.json")
        with self._lock:
            cached = self._entries.get(path)
            now = time.time()
            if cached and (now - cached[0]) < self.ttl_seconds:
                return cached[1]
            data: dict = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        data = {}
                except (OSError, json.JSONDecodeError):
                    logger.warning("invalid tenant config: %s", path)
                    data = {}
            self._entries[path] = (now, data)
            return data

    def invalidate(self, tenant_id: Optional[str] = None) -> None:
        with self._lock:
            if tenant_id is None:
                self._entries.clear()
                return
            for k in list(self._entries):
                if k.endswith(f"/{tenant_id}/config.json"):
                    self._entries.pop(k, None)


def _match_route(rules: dict, route: str):
    if not rules:
        return None
    if route in rules and isinstance(rules[route], dict):
        return rules[route]
    candidates = []
    for key, val in rules.items():
        if key.endswith("/*") and isinstance(val, dict):
            prefix = key[:-2]
            if route == prefix or route.startswith(prefix + "/"):
                candidates.append((len(prefix), val))
    if candidates:
        candidates.sort(key=lambda t: t[0], reverse=True)
        return candidates[0][1]
    if isinstance(rules.get("default"), dict):
        return rules["default"]
    return None


def _coerce(rule, fallback: RateLimit) -> RateLimit:
    if not rule:
        return fallback
    pm = int(rule.get("per_minute", fallback.per_minute))
    ph = int(rule.get("per_hour", fallback.per_hour))
    return RateLimit(per_minute=max(1, pm), per_hour=max(pm, ph))


def resolve_rate_limit(tenant_id, route, *, cache: TenantConfigCache, global_default: RateLimit = GLOBAL_DEFAULT) -> RateLimit:
    if not route:
        route = "/"
    if not tenant_id:
        return global_default
    cfg = cache.load(tenant_id) or {}
    rules = cfg.get("rate_limit") or {}
    if not isinstance(rules, dict):
        return global_default
    return _coerce(_match_route(rules, route), global_default)
