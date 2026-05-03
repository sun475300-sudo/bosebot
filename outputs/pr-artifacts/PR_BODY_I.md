## What
`/metrics` Prometheus exporter에 운영 핵심 gauge 추가 + Grafana dashboard JSON.

## Files
- `web_server.py` `/metrics` handler — scrape 시점에 db_size_bytes / chat_logs_total / auth_locked_accounts / active_sessions 새로 측정
- `src/metrics.py` — 3 gauge 등록 + 초기값 0 (첫 scrape 시 항상 노출)
- `docs/grafana_dashboard.json` — 7 panel (stat 4 + timeseries 3) 임포트용

## Tests
`tests/test_metrics_endpoint.py` — 5 cases (200 / format / default+new gauges / histogram)

## Risk
모든 gauge 측정은 try/except 보호 — 측정 실패해도 /metrics 200 유지.
