## What
audit 보고서에서 발견한 ADMIN_USERS 형식 혼동 fix.

## Bug
운영자가 `ADMIN_USERS=[{"username":"admin","password":"…"}]` 형식 (평문 `password` 키) 으로 설정해도 코드는 `password_hash` 만 체크 → 인증이 무음 실패.

## Fix
- `src/auth.py._get_admin_users()` 가 평문 `password` 키 감지 시 `hash_password()` 자동 적용 + WARN 로그 (정확한 sha256 생성 명령 안내)
- JSON 파싱 실패도 silent 폴백 → WARN 로그 + default
- list/dict 가 아닌 entry 안전하게 무시

## Tests
`tests/test_admin_users_plaintext.py` — 4 cases (자동 마이그레이션 / 잘못된 JSON / hash 통과 / 비-dict 무시)

## Risk
- 기존 password_hash 형식은 그대로 통과 (back-compat)
- 새로운 동작은 부가적 (평문도 동작하지만 WARN)
