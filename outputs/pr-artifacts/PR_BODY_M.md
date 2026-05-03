## What
PII 마스킹 opt-in (`PII_MASK_ENABLED=true`) + GDPR-style 사용자 데이터 삭제 endpoint.

## Files
- `web_server.py` — `_pii_redactor` 글로벌 + `_redact_for_log()` 헬퍼 + `DELETE /api/admin/user-data`
- `src/pii_redactor.py` — 기존 모듈 재사용 (no change)

## Endpoint
`DELETE /api/admin/user-data?session_id=...` — sentiment/conversation_v3/user_profiles 에서 해당 session_id 행 삭제, in-memory session 제거, audit_log 기록. Idempotent (없는 sid도 200).

## Tests
`tests/test_privacy.py` — 5 cases.

## Risk
순수 추가. PII_MASK_ENABLED 미설정 시 동작 동일.
