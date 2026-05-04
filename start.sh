#!/usr/bin/env bash
<<<<<<< HEAD
# =====================================================================
# Cross-platform local-run helper for Linux / macOS / WSL.
#
#   ./start.sh                # default port 8080
#   ./start.sh --port 5099    # custom port
#   PORT=5099 ./start.sh      # via environment variable
#
# Sets up a venv, installs dependencies (only when requirements.txt
# changes), and runs the dev server. For production / Docker, see
# docker-compose.yml or `make docker-up`.
# =====================================================================
set -euo pipefail

cd "$(dirname "$0")"

# ─── Resolve python ────────────────────────────────────────────────
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: python3 not found. Install Python 3.10+ from https://www.python.org/downloads/" >&2
    exit 1
fi

PY_VER=$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=$("$PY" -c 'import sys; print(sys.version_info[0])')
PY_MINOR=$("$PY" -c 'import sys; print(sys.version_info[1])')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python $PY_VER detected. This project requires Python 3.10+." >&2
    exit 1
fi

# ─── Create / reuse venv ───────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment in ./venv ..."
    "$PY" -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

# Reinstall deps when requirements.txt changes (hash-checked)
HASH_FILE="venv/.requirements.sha256"
CURRENT_HASH=$(sha256sum requirements.txt | awk '{print $1}')
if [ ! -f "$HASH_FILE" ] || [ "$(cat "$HASH_FILE")" != "$CURRENT_HASH" ]; then
    echo "Installing/updating dependencies ..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo "$CURRENT_HASH" > "$HASH_FILE"
fi

# ─── Argument / env parsing ────────────────────────────────────────
PORT="${PORT:-${CHATBOT_PORT:-8080}}"
HOST="${HOST:-${CHATBOT_HOST:-127.0.0.1}}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        --host) HOST="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,11p' "$0"
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

mkdir -p logs

echo "──────────────────────────────────────────────────────────────"
echo " Bonded Exhibition Chatbot"
echo " URL:    http://${HOST}:${PORT}"
echo " Health: http://${HOST}:${PORT}/api/health"
echo " Press Ctrl+C to stop"
echo "──────────────────────────────────────────────────────────────"

exec "$PY" web_server.py --host "$HOST" --port "$PORT"
=======
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
>>>>>>> claude/cross-platform-setup-20260428085407
