## What
audit-fix patches가 도입한 module-level state (SessionManager._sessions, src.auth._LOGIN_ATTEMPTS / _LOGIN_LOCKOUT_UNTIL) 가 테스트 사이 교차 오염될 가능성을 차단.

## File
- `tests/conftest.py` — `pytest_runtest_setup` 훅 확장하여 매 테스트 직전 SessionManager + auth lockout 초기화. 기존 `_clear_rate_limiter` 와 같은 패턴.

## Verification (sandbox)
- 84개 sample existing tests (test_classifier + test_session + test_config_manager) 통과
- audit-fix 17 cases 와 함께 실행 시 교차 영향 없음

## Risk
conftest hook 추가만 — 어떤 production 코드도 변경 없음.
