## What
Gunicorn worker count를 환경변수 미설정 시 cpu_count 기반 자동 산정 (Gunicorn 권장 (2*N)+1 공식).

## File
- `deploy/gunicorn_config.py` — `_auto_workers()` helper, `GUNICORN_THREADS` / `GUNICORN_WORKER_CLASS` env 노출, max 16 cap (cgroup 안전)

## Tests
`tests/test_gunicorn_config.py` — 5 cases (default auto / env override / threads / cap16)

## Risk
- `GUNICORN_WORKERS` 명시한 경우 동작 동일 (back-compat)
- 미설정 시 4 → cpu*2+1 (대부분 환경에서 늘어남, 메모리 사용량 사전 점검 권장)
