## What
GitHub Actions 자동 검증 파이프라인을 신설. 현재 origin은 워크플로 0개로 모든 PR이 인간 검토에 의존하고 있음.

## Files (1 commit)
- `.github/workflows/ci.yml` — Python 3.10/3.11/3.12 matrix · lint(flake8/ruff/black) + pytest --cov
- `.github/workflows/security.yml` — bandit + pip-audit + safety, 매주 월요일 cron
- `.github/dependabot.yml` — pip / github-actions / docker, 주간 스케줄, flask-stack/test-tools 그룹화

## Verification
- 3개 YAML 파일 schema 검증 (python yaml safe_load)
- `concurrency: cancel-in-progress` + `timeout-minutes` 설정으로 비용 제어
- ruff/black 은 baseline 정비 전까지 `continue-on-error` (informational)

## Risk
순수 추가 — 기존 코드 0줄 변경. 머지 즉시 차후 PR부터 자동 CI 가동.
