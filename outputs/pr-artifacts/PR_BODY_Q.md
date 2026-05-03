## What
Response 캐시 레이어 — L1 in-memory LRU + L2 Redis 옵션.

## Files
- `src/response_cache.py` (신규) — OrderedDict LRU, TTL, redis fallback
- `web_server.py` — admin stats / flush endpoints

## Env
- `RESPONSE_CACHE_SIZE` (256) · `RESPONSE_CACHE_TTL` (300s) · `REDIS_URL` (optional)

## API
- `GET  /api/admin/cache/response/stats`  — size/hit/miss/hit_rate/l2_redis
- `POST /api/admin/cache/response/flush`  — 전체 무효화

## Tests
`tests/test_response_cache.py` — 8 cases (set/get/miss/LRU/TTL/invalidate/stats/admin).
