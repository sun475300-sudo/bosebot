## What
End-to-End 시나리오 테스트 9 cases — 모듈 간 사이드이펙트까지 검증.

## File
`tests/test_e2e_scenarios.py`

## Coverage
- `chat → DB 저장 → /api/admin/logs` 사용자 query 노출
- `/api/auth/me` JWT decode + garbage token 거부 (TESTING off 상태)
- `/api/feedback` `feedback_id` 반환 + 영속화
- `/api/admin/analytics` `peak_hours.hours` schema
- `/api/session/new → 3 chats → /profile.topics` 누적
- 임의 session_id 자동 등록 (Patch C 의존, 미적용 환경에서도 graceful)
- `/api/faq/reload` `faq_count >= 1`
- 35 rapid /api/chat → 429 발생

## Risk
독립 추가, 기존 테스트와 conftest hook 으로 격리.
