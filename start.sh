#!/usr/bin/env bash
# ============================================================
# 보세전시장 챗봇 - Linux/Mac 개발용 1-라인 실행 스크립트
# ------------------------------------------------------------
# 사용법:
#   ./start.sh             # 8080 포트로 실행 (.env 자동 로드)
#   ./start.sh --port 5000 # 포트 변경
#   PORT=9000 ./start.sh   # 환경변수로 포트 지정
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8080}"

# CLI flags (--port 5000)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# //; s/^#//'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Python check
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "✗ python3가 없습니다. https://www.python.org/downloads/ 에서 3.10+ 설치 후 다시 실행." >&2
  exit 1
fi

# venv 생성 (없으면)
if [[ ! -d "$VENV_DIR" ]]; then
  echo "▸ venv 생성: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# venv 활성화
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# 의존성 (requirements.txt 변경 감지 → 자동 재설치)
REQ_HASH_FILE="$VENV_DIR/.req.sha256"
CUR_HASH="$(sha256sum requirements.txt 2>/dev/null | awk '{print $1}' || shasum -a 256 requirements.txt | awk '{print $1}')"
if [[ ! -f "$REQ_HASH_FILE" ]] || [[ "$(cat "$REQ_HASH_FILE")" != "$CUR_HASH" ]]; then
  echo "▸ pip install -r requirements.txt"
  pip install --upgrade pip --quiet
  pip install -r requirements.txt --quiet
  echo "$CUR_HASH" > "$REQ_HASH_FILE"
fi

# .env 자동 로드 (있으면)
if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
  echo "▸ .env loaded"
else
  echo "▸ .env 없음 — .env.example 복사 권장: cp .env.example .env"
fi

echo "▸ 보세전시장 챗봇 시작: http://127.0.0.1:${PORT}"
exec python web_server.py --port "$PORT"
