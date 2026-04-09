# 보세전시장 챗봇 — 배포 가이드

## 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 2코어 | 4코어 |
| RAM | 2GB | 4GB |
| 디스크 | 10GB | 20GB (SSD) |
| OS | Ubuntu 20.04+ | Ubuntu 22.04 LTS |
| Docker | 24.0+ | 최신 |
| Docker Compose | v2.20+ | 최신 |

## 빠른 시작 (5분)

```bash
# 1. 레포 클론
git clone https://github.com/sun475300-sudo/bonded-exhibition-chatbot-data.git
cd bonded-exhibition-chatbot-data

# 2. 환경 변수 설정
cp .env.example .env
nano .env  # API 키, DB 경로 등 수정

# 3. 배포
chmod +x deploy.sh
./deploy.sh deploy

# 4. 확인
./deploy.sh status
curl http://localhost/health
```

## 아키텍처

```
[클라이언트] → [Nginx:80/443] → [Gunicorn:8080] → [Flask App]
                                       ↓
                                   [Redis:6379]   [SQLite DB]
```

- **Nginx**: 리버스 프록시, SSL, 정적 파일 서빙, Rate Limiting
- **Gunicorn**: WSGI 서버 (4 워커, sync 모드)
- **Flask**: 챗봇 API (FAQ 검색, NLP 분류, LLM 연동)
- **Redis**: 세션 캐시, FAQ 응답 캐시
- **SQLite**: 대화 로그, 사용자 분석

## deploy.sh 명령어

| 명령어 | 설명 |
|--------|------|
| `./deploy.sh deploy` | 신규 배포 (빌드 + 시작) |
| `./deploy.sh update` | 무중단 업데이트 (백업→빌드→롤링) |
| `./deploy.sh rollback` | 이전 버전으로 복원 |
| `./deploy.sh status` | 서비스 상태 + 리소스 확인 |
| `./deploy.sh logs [서비스] [줄수]` | 로그 보기 |
| `./deploy.sh backup` | DB 수동 백업 |
| `./deploy.sh cleanup` | Docker 리소스 정리 |

## 환경 변수 (.env)

```env
# 필수
CHATBOT_PORT=8080
CHATBOT_HOST=0.0.0.0
CHATBOT_LOG_LEVEL=INFO
CHATBOT_DB_PATH=logs/chat_logs.db

# 선택 (LLM 연동 시)
ANTHROPIC_API_KEY=sk-ant-xxx
CHATBOT_API_KEYS=key1,key2

# Gunicorn 튜닝
GUNICORN_WORKERS=4
GUNICORN_TIMEOUT=120

# Redis
REDIS_URL=redis://redis:6379/0
```

## SSL 인증서 설정

```bash
# Certbot으로 Let's Encrypt 인증서 발급
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --standalone -d your-domain.com

# docker-compose.yml에서 nginx 볼륨 주석 해제:
# - /etc/letsencrypt:/etc/letsencrypt:ro

# deploy/nginx.conf에서 SSL 블록 주석 해제 후:
./deploy.sh update
```

## 모니터링

**헬스 체크 엔드포인트:**

| 엔드포인트 | 설명 |
|------------|------|
| `GET /health` | 서비스 상태 (200=정상) |
| `GET /api/v1/stats` | API 통계 |
| `GET /metrics` | Prometheus 메트릭 |

**Grafana 대시보드:** `deploy/grafana_dashboard.json`을 Grafana에 import하면 즉시 사용 가능

## 백업 & 복원

자동 백업은 `deploy.sh update` 실행 시 자동으로 생성됩니다. 수동 백업은 `./deploy.sh backup`으로 실행하세요. 최근 10개 백업이 유지되며, 오래된 백업은 자동 삭제됩니다.

복원은 `./deploy.sh rollback`으로 가장 최근 백업을 사용합니다.

## 문제 해결

**서비스가 시작되지 않을 때:**
```bash
./deploy.sh logs chatbot 200    # 챗봇 로그
./deploy.sh logs nginx 50       # Nginx 로그
docker compose ps               # 컨테이너 상태
```

**포트 충돌:**
```bash
sudo lsof -i :80   # 80포트 사용 프로세스 확인
sudo lsof -i :8080
```

**메모리 부족:**
```bash
docker stats --no-stream        # 컨테이너 메모리 확인
# docker-compose.yml에서 memory limits 조정
```

**DB 잠금 오류:**
```bash
docker compose exec chatbot sqlite3 logs/chat_logs.db ".tables"
docker compose restart chatbot
```
