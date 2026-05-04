# Track SS — Per-tenant rate-limit override

`src/tenant_rate_limit.py` reads `tenants/<id>/config.json` and resolves
the effective `RateLimit` for any (tenant, route). Match precedence:
exact → longest wildcard prefix → tenant default → global default.
TTL-cached. 6 tests pass. No new deps.
