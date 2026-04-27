@echo off
cd /d E:\GitHub\bonded-exhibition-chatbot-data
start /b python web_server.py --port 5099 --host 127.0.0.1
ping -n 35 127.0.0.1 >nul
start http://127.0.0.1:5099/
