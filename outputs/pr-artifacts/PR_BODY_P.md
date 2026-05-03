## What
A/B testing framework — deterministic variant assignment + conversion tracking.

## Files
- `src/experiments.py` (신규) — ExperimentManager, SHA-256 기반 결정적 분기
- `config/experiments.yml` (신규) — 2 샘플 (response_template_v2 active, faq_threshold_low inactive)
- `web_server.py` — admin endpoints + public conversion endpoint

## API
- `GET  /api/admin/experiments`              — exposures + conversion_rate
- `POST /api/admin/experiments/reload`       — yml 재로드
- `POST /api/experiments/{name}/conversion`  — public 전환 트래킹

## Tests
7 cases (결정성 / 분포 / inactive / 통계).
