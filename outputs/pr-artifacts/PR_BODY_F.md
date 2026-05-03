## What
audit fix patches 적용 후 도입된 환경변수 (`AUTH_*`, `*_RPM`) 와 보안 점검 항목을 운영자가 한 페이지에서 확인하도록 가이드 추가.

## File
- `docs/OPERATIONS.md` (135 lines) — 5 sections
  1. 환경변수 한눈에 보기 (필수 / 선택 / 신규 보안)
  2. 운영 보안 체크리스트 (8 items)
  3. 비밀 회전 절차 (JWT / admin / lockout)
  4. 운영 명령 모음
  5. 장애 대응 1차 점검표
- `README.md` — 상단에 OPERATIONS.md 링크 1줄 추가

## Risk
순수 docs — 코드 변경 0.
