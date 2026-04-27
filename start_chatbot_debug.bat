@echo off
cd /d E:\GitHub\bonded-exhibition-chatbot-data
echo Starting chatbot...
python web_server.py --port 5099 --host 127.0.0.1
pause
