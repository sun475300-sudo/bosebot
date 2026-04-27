# ============================================================
# 보세전시장 챗봇 - 자주 쓰는 명령 모음
# ============================================================
# `make` 또는 `make help` 로 명령 목록 확인.
# ============================================================

.PHONY: help install run test test-fast lint clean docker-build docker-up docker-down docker-logs docker-restart docker-prod-up env-check

PYTHON ?= python
PORT   ?= 8080

help: ## 사용 가능한 명령 보기
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## 의존성 설치 (requirements.txt)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

run: ## 로컬 개발 서버 실행 (PORT=$(PORT))
	$(PYTHON) web_server.py --port $(PORT)

test: ## 전체 테스트 (pytest)
	$(PYTHON) -m pytest tests/ -v

test-fast: ## 빠른 테스트 (느린 마커 제외)
	$(PYTHON) -m pytest tests/ -v -m "not slow"

lint: ## flake8 린트 (CI와 동일 규칙)
	$(PYTHON) -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	$(PYTHON) -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

clean: ## 캐시/임시 파일 삭제
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

env-check: ## .env 존재 + 필수 변수 채워졌는지 확인
	@test -f .env || (echo "✗ .env 없음. cp .env.example .env 후 채우세요." && exit 1)
	@grep -q '^JWT_SECRET_KEY=change-me' .env && echo "⚠  JWT_SECRET_KEY가 기본값입니다. 변경하세요!" || true
	@echo "✓ .env 존재"

docker-build: ## 이미지 빌드 (캐시 사용)
	docker compose build

docker-up: ## 백그라운드 실행 + 헬스체크 대기
	docker compose up -d
	@echo "▸ 헬스체크 대기 (최대 60초)..."
	@for i in $$(seq 1 60); do \
	  status=$$(docker inspect -f '{{.State.Health.Status}}' bonded-chatbot 2>/dev/null || echo "starting"); \
	  if [ "$$status" = "healthy" ]; then echo "✓ healthy ($${i}s)"; exit 0; fi; \
	  sleep 1; \
	done; \
	echo "⚠ 60초 내 healthy 미달성. docker compose logs 로 확인하세요."

docker-down: ## 컨테이너 종료 (볼륨 유지)
	docker compose down

docker-logs: ## 실시간 로그 (Ctrl+C로 종료)
	docker compose logs -f --tail=100

docker-restart: docker-down docker-up ## 재시작

docker-prod-up: ## nginx + redis 포함 풀스택 (운영용)
	docker compose -f docker-compose.production.yml up -d
