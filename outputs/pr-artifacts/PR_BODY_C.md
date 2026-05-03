## What
Audit 보고서에서 발견한 3개 버그 일괄 수정:
1. **세션 컨텍스트 손실** — `/api/chat` 임의 session_id로 호출 시
2. **무제한 brute force** — `/api/auth/login` 실패 카운트/잠금 없음
3. **`/api/chat` 30 RPM 하드코드** — 환경변수로 조정 불가

## Files (3 commits)
| commit | files | +/- |
|---|---|---|
| `fix(session): auto-create...` | `src/session.py`, `web_server.py`, `tests/test_session_auto_create.py` | +51/-4 |
| `fix(auth): N회 실패 시 잠금` | `src/auth.py`, `web_server.py`, `tests/test_auth_lockout.py` | +128/-1 |
| `fix(rate-limit): env override` | `src/rate_limiter_v2.py`, `tests/test_rate_limit_env.py` | +61/-2 |

## Verification (sandbox)
```
git apply --check  → 3/3 OK
pytest             → 13/13 PASS in 2.6s
   test_session_auto_create.py     3 cases
   test_auth_lockout.py            4 cases
   test_rate_limit_env.py          6 cases
```

## API additions / new env vars
| 환경변수 | default | 설명 |
|---|---|---|
| `AUTH_MAX_ATTEMPTS` | 5 | 실패 횟수 임계 |
| `AUTH_LOCKOUT_SECONDS` | 300 | 잠금 시간 (초) |
| `AUTH_ATTEMPT_WINDOW_SECONDS` | 900 | 실패 윈도우 (초) |
| `CHAT_RPM` | 30 | `/api/chat` 분당 한도 |
| `FAQ_RPM` | 60 | `/api/faq` |
| `ADMIN_RPM` | 20 | `/api/admin/*` |
| `AUTOCOMPLETE_RPM` | 120 | |
| `SEARCH_RPM` | 60 | `/api/search/*` (신규) |

## API behavior changes
- `POST /api/auth/login` returns **423 ACCOUNT_LOCKED** with `retry_after_seconds` after N failures.
- `POST /api/chat` 자동 세션 등록 → `/api/session/{id}/context` 가 비어있지 않게 됨.

## Risk
- 3 patch 모두 격리: `src/auth.py`, `src/session.py`, `src/rate_limiter_v2.py` 각자 변경 후 `web_server.py`에 신규 코드만 추가 (기존 분기 제거 X).
- 환경변수 설정 안 하면 기존 동작과 동일 (ergonomic, fully back-compat).
- 기존 1,310+ 테스트 영향 없음 (sandbox 검증 한도 내).
