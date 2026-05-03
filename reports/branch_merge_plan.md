# Branch Merge Plan — bonded-exhibition-chatbot-data

생성: 2026-05-03

## 분류 결과

총 19개 브랜치 (main 제외)

### 이미 main에 머지된 브랜치 (3개) — 삭제 권장
- `claude/angry-dirac-f983f1`
- `claude/relaxed-hoover-bcde14`
- `claude/ui-polish-20260428-085757`

### 충돌 없이 fast-forward 머지 가능 (6개) — 우선 처리
- `claude/cross-platform-setup-20260428-085238` (ahead=1, behind=1)
- `claude/cross-platform-setup-20260428085407` (ahead=1, behind=1)
- `claude/fix-bot-startup-deps` (ahead=4, behind=8)
- `claude/track-CC-websocket-202605030001` (ahead=1, behind=0)
- `claude/track-EE-feedback-loop-202605030010` (ahead=1, behind=0)
- `claude/ui-polish-20260428085407` (ahead=1, behind=1)

### main과 충돌 가능 (10개) — 수동 검토 필요
- `claude/fix-jwt-cors-202604271700` (ahead=16, behind=8) ⚠
- `claude/fix-tests-ci-green` (ahead=8, behind=8)
- `claude/fix-ui-scroll-202604271500` (ahead=14, behind=8)
- `claude/fix-ui-sidebar-202604271600` (ahead=15, behind=8)
- `claude/fix-vector-search-w293` (ahead=9, behind=8)
- `claude/h4-st-fixture-mock-202604271800` (ahead=17, behind=8) ⚠
- `claude/master-plan-bonded` (ahead=4, behind=8)
- `claude/perf-stability-202604271200` (ahead=14, behind=8)
- `claude/phase5-ops-202604271300` (ahead=10, behind=8)
- `claude/phase7-tests-202604271400` (ahead=13, behind=8)

## 권장 머지 순서

1. **특허 수정 (이번 변경)** — main에 직접 commit + push  ← 최우선
2. **MERGED 그룹** — 브랜치만 삭제 (`git branch -d <name>`)
3. **CLEAN 그룹 6개** — 순서대로 `git merge --no-ff`
4. **CONFLICT 그룹 10개** — 사이즈 작은 것(`master-plan-bonded`)부터 수동 rebase·merge

## 메모

- 모든 CONFLICT는 main이 8개 commit 앞서 있어서 발생 — 즉, 최근 main 변경(예: 이번 사이클 정리 커밋)과의 단순 충돌일 가능성이 높음.
- `pytest tests/test_patent_regression.py`는 머지 후마다 항상 통과해야 함.
