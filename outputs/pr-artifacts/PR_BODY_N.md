## What
백업 SHA-256 manifest + S3/MinIO 옵션 + restore_db.sh 신설.

## Files
- `scripts/backup_db.sh` — 보강: manifest JSON, S3_BUCKET / MINIO_ALIAS env, retention 30d
- `scripts/restore_db.sh` (신규) — checksum 검증 후 복원, --latest / --list 옵션
- `tests/test_backup_restore.py` — 4 cases

## Risk
기존 backup 사용자 영향 없음 (옵션 모두 env-driven).
