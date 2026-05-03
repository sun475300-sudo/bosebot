# 🩹 Audit Fix Patches — 3 bugs

`/api/chat` 임의 session_id 컨텍스트 손실 / 로그인 무제한 brute force / `/api/chat` 30 RPM 하드코드 — [audit 보고서 참고].

## 🚀 한 줄 적용

```bat
:: Windows
patches\APPLY_PATCHES.bat
```
```bash
# Linux / macOS / WSL
bash patches/apply_patches.sh
```

스크립트는 다음을 자동 수행:
1. 3개 patch 충돌 검사 (`git apply --check`)
2. 순차 적용
3. 신규 13개 pytest 실행
4. `git status` 표시

이후 정상이면:
```bash
git add -A && git commit -m "fix: apply 3 audit patches"
git push origin <your-branch>
```

## 📋 변경 요약

| # | 파일 | 함수/클래스 | 추가된 환경변수 |
|---|---|---|---|
| **0001** | `src/session.py`, `web_server.py` (chat) | `SessionManager.create_session(session_id=)`, `ensure_session()` | — |
| **0002** | `src/auth.py`, `web_server.py` (login) | `is_locked_out()`, `record_failed_login()`, `reset_failed_logins()` | `AUTH_MAX_ATTEMPTS=5` · `AUTH_LOCKOUT_SECONDS=300` · `AUTH_ATTEMPT_WINDOW_SECONDS=900` |
| **0003** | `src/rate_limiter_v2.py` | `AdvancedRateLimiter._build_default_limits()` | `CHAT_RPM` · `FAQ_RPM` · `ADMIN_RPM` · `AUTOCOMPLETE_RPM` · `SEARCH_RPM` |

## 🧪 검증

각 patch는 격리된 테스트 모듈을 가지며 (총 13 cases), 기존 1,310+ 테스트와 충돌하지 않도록 작성됨:

```
tests/test_session_auto_create.py     3 cases
tests/test_auth_lockout.py            4 cases
tests/test_rate_limit_env.py          6 cases
─────────────────────────────────────────────
                                     13 passed in 2.6s
```

## 🆕 새 동작 명세

### Patch 0001 — session auto-create
- `POST /api/chat` 진입 시 `data.session_id`가 SessionManager에 없으면 자동 등록
- `/api/session/{id}/context` 가 빈 응답 대신 실제 K-V context 배열 반환
- `/api/session/{id}/profile.topics` 가 누적 (3턴 → topics 3개)

### Patch 0002 — brute-force lockout
- 5회 연속 실패 → 6번째부터 `423 ACCOUNT_LOCKED`
- 응답 본문: `{"error_code":"ACCOUNT_LOCKED", "retry_after_seconds": N}`
- 잠금 중에는 올바른 비밀번호도 423
- 성공 로그인 시 카운터 리셋
- 잠금 시간 경과 후 자동 해제

### Patch 0003 — rate-limit env
- `CHAT_RPM=180 docker compose up -d` 한 줄로 30 → 180 RPM 변경
- 잘못된 값(`"abc"`, `0`, `-5`)은 안전한 default로 폴백
- 기존 `endpoint_limits=` kwarg 명시는 여전히 우선 (back-compat)

## ↩️ 되돌리기

```bash
git apply -R patches/0003-rate-limit-env.patch
git apply -R patches/0002-brute-force-lockout.patch
git apply -R patches/0001-session-auto-create.patch
rm tests/test_session_auto_create.py tests/test_auth_lockout.py tests/test_rate_limit_env.py
```
