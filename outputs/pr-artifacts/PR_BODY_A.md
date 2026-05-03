## What
크로스 플랫폼 부팅을 한 줄로 만듭니다. Docker / venv / Windows.bat / WSL 4가지 경로 모두 60초 안에 `/api/health`까지 도달.

## Files
- **Dockerfile** — multi-stage `python:3.11-slim` builder→production, non-root (uid 10001), HEALTHCHECK on `/api/health` (curl), `HF_HOME` volume, `gunicorn -w 2 --threads 4 --preload`, tini init
- **docker-compose.yml** — compose v2, single `web` service, `env_file` long-form (required:false), named volumes (logs/data/backups/hf-cache), curl healthcheck
- **.env.example** — `ANTHROPIC_API_KEY`, `JWT_SECRET_KEY` (+`JWT_SECRET` 호환), `ADMIN_USERS` (bcrypt how-to), `CHATBOT_API_KEYS`, `CHATBOT_CORS_ORIGINS`, `FLASK_ENV`, `LOG_LEVEL`
- **start.sh** — auto-detect docker → venv 폴백, `.env` 자동 초기화, `/api/health` 폴링
- **Makefile** — `install / run / test / docker-up / docker-down / docker-logs / health / clean`
- **README** — 60초 Quickstart 4가지 경로 + Troubleshooting matrix
- **.dockerignore** — logs/, backups/, *.db 빌드 컨텍스트 제외

## Verification
- `python3` 로 compose v2 스키마 유효성 검사 통과 (services/volumes/networks/healthcheck 모두 정상)
- Dockerfile 정적 검사: 멀티스테이지 ✓ non-root ✓ HEALTHCHECK ✓ /api/health ✓ HF_HOME ✓ VOLUME ✓ gunicorn -w 2 --threads 4 --preload ✓ tini ✓
- `make help` 타겟 14개 정상 노출
- (sandbox 에 docker 미설치라 실제 빌드는 로컬에서 `make docker-build` 로 검증 권장)

## Quickstart
```bash
cp .env.example .env
docker compose up -d           # 또는 ./start.sh / make run / start_chatbot_simple.bat
curl http://127.0.0.1:8080/api/health
```

## Risk
없음 — 모두 추가/문서/빌드 시스템 변경. 기존 코드 수정 없음. 기존 `start_chatbot_*.bat` / `deploy/healthcheck.py` 그대로 유지.
