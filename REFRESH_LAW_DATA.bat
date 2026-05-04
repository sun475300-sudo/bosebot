@echo off
REM ========================================================================
REM  REFRESH_LAW_DATA.bat
REM  Refresh national law + admRul (administrative rule) cache.
REM
REM  Pulls the latest text for monitored laws (Customs Act etc.) and the
REM  bonded-exhibition-operation notice (admRulSeq=2100000276240) from
REM  law.go.kr Open API and updates data/legal_references.json.
REM
REM  Optional environment variable:
REM    LAW_API_OC : Open API authentication key (your law.go.kr email id)
REM ========================================================================
chcp 65001 > nul
cd /d E:\GitHub\bonded-exhibition-chatbot-data
echo.
echo === Refreshing law and admRul data ===
echo.
python scripts\refresh_law_data.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] refresh failed - check network and try again
    pause
    exit /b 1
)
echo.
echo [OK] refresh complete
echo See data\legal_references.json and data\law_sync.db for details.
echo.
pause
