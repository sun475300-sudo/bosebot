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

exec "$PY" web_server.py --host "$HOST" --