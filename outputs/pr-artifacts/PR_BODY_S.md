## What
Per-request trace_id (OpenTelemetry-optional).

## Files
- `src/tracing.py` — opentelemetry 미설치 시 graceful (32-hex token_hex만 발급)
- `web_server.py` — before/after_request hook + `GET /api/admin/trace/sample`

## Behavior
- 모든 응답에 `X-Trace-Id` 헤더
- 클라이언트가 보낸 `X-Trace-Id` 를 그대로 전파
- `OTEL_EXPORTER_OTLP_ENDPOINT` 설정 시 OTLP 자동 export

## Tests
`tests/test_tracing.py` — 5 cases
