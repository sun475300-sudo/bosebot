## What
Static-analysis baseline — ruff strict + bandit + pre-commit hooks.

## Files
- `pyproject.toml` — ruff `select=[E,F,W,I,N,S,B,A]`, line-length 110, legacy ignores
- `.bandit.yml` — audited skips (B101/B404/B603/B607), exclude tests/data/logs
- `.pre-commit-config.yaml` — ruff v0.6.9 + bandit 1.7.10 + standard hooks

기존 코드는 baseline ignore 로 grandfather → 신규 코드부터 strict 적용.
CI (Track D) 의 ruff/black step 은 informational 이라 충돌 없음.

## Tests
`tests/test_static_analysis_config.py` — 4 cases (config 파일 파싱 검증)
