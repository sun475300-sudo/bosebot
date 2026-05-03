## What
Audit-log paged search API.

## File
`web_server.py` 추가 endpoint:
`GET /api/admin/audit/search?actor=&action=&resource_type=&from=&to=&limit=&offset=`
- limit max 500, offset 검증, ORDER BY id DESC
- details JSON 자동 파싱
- AUDIT_DB_PATH env 로 경로 override
- DB 없을 때 graceful empty

기존 `/api/admin/audit` 동작은 그대로 (back-compat).

## Tests
`tests/test_audit_search.py` — 7 cases
