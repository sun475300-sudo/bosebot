## What
운영 자동화 스크립트 모음 — health probe / DB 백업 / log retention.

## Files
- `scripts/health_check.sh` — `/api/health` 폴링 + Slack webhook 알림 (`ALERT_WEBHOOK` env)
- `scripts/backup_db.sh` — sqlite3 .backup → gzip → 7일 retention (`BACKUP_RETENTION_DAYS` env)
- `scripts/rotate_logs.py` — chat_logs 90일 retention + VACUUM, `--dry-run` / `--days` / `LOG_RETENTION_DAYS` env
- `scripts/CRONTAB.example` — Linux crontab 3 entries
- `scripts/WINDOWS_TASKS.md` — PowerShell `Register-ScheduledTask` 가이드

## Tests
`tests/test_rotate_logs.py` — 4 cases (tmp_path 격리: dry-run / actual delete / invalid days / missing db)

## Risk
모든 스크립트 read 또는 격리된 file 작업만. 셸 syntax 검증 OK (`bash -n`).
