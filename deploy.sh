#!/bin/bash
# ============================================
# 보세전시장 챗봇 - 배포 자동화 스크립트
# 사용법: ./deploy.sh [deploy|update|rollback|status|logs|backup]
# ============================================
set -euo pipefail

# --- 설정 ---
APP_NAME="bonded-chatbot"
COMPOSE_FILE="docker-compose.yml"
BACKUP_DIR="./backups"
LOG_FILE="deploy.log"
MAX_BACKUPS=10
HEALTH_URL="http://localhost/health"
HEALTH_TIMEOUT=60

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"; }
ok()  { echo -e "${GREEN}✓${NC} $1" | tee -a "$LOG_FILE"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1" | tee -a "$LOG_FILE"; }
err() { echo -e "${RED}✗${NC} $1" | tee -a "$LOG_FILE"; }

# --- 사전 검사 ---
preflight_check() {
    log "사전 검사 시작..."

    command -v docker >/dev/null 2>&1 || { err "Docker가 설치되지 않았습니다."; exit 1; }
    command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || { err "Docker Compose가 설치되지 않았습니다."; exit 1; }

    [ -f "$COMPOSE_FILE" ] || { err "$COMPOSE_FILE 파일을 찾을 수 없습니다."; exit 1; }
    [ -f "Dockerfile" ] || { err "Dockerfile을 찾을 수 없습니다."; exit 1; }
    [ -f ".env.example" ] && [ ! -f ".env" ] && { warn ".env 파일이 없습니다. .env.example을 복사하세요: cp .env.example .env"; }

    ok "사전 검사 통과"
}

# --- 배포 ---
deploy() {
    preflight_check
    log "=== 신규 배포 시작 ==="

    # 이미지 빌드
    log "Docker 이미지 빌드 중..."
    docker compose -f "$COMPOSE_FILE" build --no-cache
    ok "이미지 빌드 완료"

    # 컨테이너 기동
    log "서비스 시작 중..."
    docker compose -f "$COMPOSE_FILE" up -d
    ok "서비스 시작 완료"

    # 헬스 체크 대기
    wait_for_health

    log "=== 배포 완료 ==="
    status
}

# --- 업데이트 (무중단) ---
update() {
    preflight_check
    log "=== 무중단 업데이트 시작 ==="

    # 백업
    backup

    # 현재 이미지 태그 저장 (롤백용)
    CURRENT_IMAGE=$(docker inspect --format='{{.Image}}' "$APP_NAME" 2>/dev/null || echo "none")
    echo "$CURRENT_IMAGE" > "$BACKUP_DIR/.last_image"

    # 새 이미지 빌드
    log "새 이미지 빌드 중..."
    docker compose -f "$COMPOSE_FILE" build chatbot
    ok "빌드 완료"

    # 롤링 업데이트
    log "챗봇 서비스 업데이트 중..."
    docker compose -f "$COMPOSE_FILE" up -d --no-deps chatbot

    # 헬스 체크
    if wait_for_health; then
        ok "업데이트 성공"
    else
        err "헬스 체크 실패! 롤백을 시작합니다..."
        rollback
        exit 1
    fi

    # 미사용 이미지 정리
    docker image prune -f >/dev/null 2>&1

    log "=== 업데이트 완료 ==="
    status
}

# --- 롤백 ---
rollback() {
    log "=== 롤백 시작 ==="

    if [ -f "$BACKUP_DIR/.last_image" ]; then
        PREV_IMAGE=$(cat "$BACKUP_DIR/.last_image")
        log "이전 이미지로 롤백: $PREV_IMAGE"
    fi

    # DB 복원
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.db.bak 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ]; then
        log "데이터베이스 복원: $LATEST_BACKUP"
        docker compose -f "$COMPOSE_FILE" exec -T chatbot \
            cp "/app/backups/$(basename "$LATEST_BACKUP")" /app/logs/chat_logs.db 2>/dev/null || true
    fi

    # 서비스 재시작 (이전 이미지)
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d

    wait_for_health
    log "=== 롤백 완료 ==="
}

# --- 상태 확인 ---
status() {
    echo ""
    log "=== 서비스 상태 ==="
    docker compose -f "$COMPOSE_FILE" ps
    echo ""

    # 헬스 체크
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        ok "API 응답: HTTP $HTTP_CODE"
    else
        warn "API 응답: HTTP $HTTP_CODE"
    fi

    # 리소스 사용량
    echo ""
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
        $(docker compose -f "$COMPOSE_FILE" ps -q) 2>/dev/null || true
}

# --- 로그 ---
show_logs() {
    SERVICE=${1:-chatbot}
    LINES=${2:-100}
    docker compose -f "$COMPOSE_FILE" logs --tail="$LINES" -f "$SERVICE"
}

# --- 백업 ---
backup() {
    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

    log "데이터 백업 중..."

    # DB 백업
    docker compose -f "$COMPOSE_FILE" exec -T chatbot \
        cp /app/logs/chat_logs.db "/app/backups/chat_logs_${TIMESTAMP}.db.bak" 2>/dev/null || true

    # 오래된 백업 정리
    ls -t "$BACKUP_DIR"/*.db.bak 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f 2>/dev/null || true

    ok "백업 완료: chat_logs_${TIMESTAMP}.db.bak"
}

# --- 헬스 체크 대기 ---
wait_for_health() {
    log "헬스 체크 대기 중 (최대 ${HEALTH_TIMEOUT}초)..."

    for i in $(seq 1 "$HEALTH_TIMEOUT"); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            ok "헬스 체크 통과 (${i}초)"
            return 0
        fi
        sleep 1
    done

    err "헬스 체크 실패 (${HEALTH_TIMEOUT}초 초과)"
    return 1
}

# --- 정리 ---
cleanup() {
    log "Docker 리소스 정리 중..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
    docker image prune -f
    ok "정리 완료"
}

# --- 메인 ---
case "${1:-help}" in
    deploy)   deploy ;;
    update)   update ;;
    rollback) rollback ;;
    status)   status ;;
    logs)     show_logs "${2:-chatbot}" "${3:-100}" ;;
    backup)   backup ;;
    cleanup)  cleanup ;;
    *)
        echo "사용법: $0 {deploy|update|rollback|status|logs|backup|cleanup}"
        echo ""
        echo "  deploy   - 신규 배포 (빌드 + 시작)"
        echo "  update   - 무중단 업데이트 (백업 → 빌드 → 롤링 업데이트)"
        echo "  rollback - 이전 버전으로 롤백"
        echo "  status   - 서비스 상태 확인"
        echo "  logs     - 로그 보기 (예: $0 logs chatbot 200)"
        echo "  backup   - 데이터베이스 백업"
        echo "  cleanup  - Docker 리소스 정리"
        ;;
esac
