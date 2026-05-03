## What
JWT 사용자별 분당 요청 한도 (per-user RPM cap).

## Files
- `src/per_user_rate_limit.py` (신규) — sliding window per username
- `web_server.py` — `GET / POST /api/admin/rate-limit/<username>` 추가

## Env
- `USER_RPM_DEFAULT` (60) · `USER_RPM_PREMIUM` (300)
- 사용자별 override 는 `POST /api/admin/rate-limit/<u> {"rpm": N}` 으로 설정

## Tests
9 cases. Multi-process 환경은 redis 백엔드 추후 확장.
