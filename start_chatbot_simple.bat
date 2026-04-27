@echo off
chcp 65001 >nul
setlocal
cd /d "E:\GitHub\bonded-exhibition-chatbot-data"

echo === bonded chatbot — local launcher ===
echo.

echo [1/4] Pull main (fast-forward only)...
git fetch origin main 2>nul
git pull --ff-only origin main 2>nul
echo.

echo [2/4] Ensuring core dependencies...
python -m pip install -q flask flask-cors gunicorn anthropic sentence-transformers torch pyjwt python-dotenv pyyaml requests
echo.

echo [3/4] Starting bot on port 5099 (sentence-transformers ~30s)...
if not exist logs mkdir logs
set "PYTHONUTF8=1"
start "bonded-chatbot" /B python web_server.py --port 5099 --host 127.0.0.1 > logs\chatbot_local.log 2> logs\chatbot_local.err
echo Bot launched in background.
echo.

echo [4/4] Waiting 35s, then opening browser...
timeout /t 35 /nobreak >nul
start http://127.0.0.1:5099/
echo.

echo ================================================
echo  URL    : http://127.0.0.1:5099/
echo  Health : http://127.0.0.1:5099/api/health
echo  Stats  : http://127.0.0.1:5099/api/v1/stats
echo  Stop   : taskkill /F /IM python.exe   (모든 python 종료)
echo  Log    : type logs\chatbot_local.log
echo  Err    : type logs\chatbot_local.err
echo ================================================
pause
