## What
chat_logs 기반 z-score 이상 탐지 + Slack 웹훅 알림.

## File
`scripts/detect_anomalies.py`
- 24h baseline 대비 최근 1h 의 hourly_total + hourly_escalations z-score
- Exit codes: 0=ok/insufficient, 1=db missing, 2=anomaly
- env: `ANOMALY_WINDOW_HOURS=24`, `ANOMALY_Z_THRESHOLD=3.0`, `ANOMALY_WEBHOOK_URL`
- crontab 권장: `*/15 * * * *`

## Tests
`tests/test_anomaly_detection.py` — 4 cases (normal / spike / insufficient / missing)
