@echo off
REM ================================================================
REM  Register a Windows Task Scheduler job that runs the law/admrul
REM  refresh every 6 hours, even if Cowork / chatbot is not running.
REM
REM  Run from this directory (the repo root). Requires permission to
REM  call schtasks.exe (a normal user account is sufficient for HOURLY
REM  per-user tasks). If you see Access denied, right-click and
REM  Run as administrator.
REM ================================================================

setlocal
set TASK_NAME=BondedChatbotLawRefresh
set REPO_DIR=%~dp0
if "%REPO_DIR:~-1%"=="\" set REPO_DIR=%REPO_DIR:~0,-1%
set SCRIPT=%REPO_DIR%\scripts\scheduled_refresh.py

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: python.exe not found on PATH. Install Python 3.10+ first.
  pause
  exit /b 1
)

if not exist "%SCRIPT%" (
  echo ERROR: %SCRIPT% not found.
  pause
  exit /b 1
)

echo Registering scheduled task: %TASK_NAME%
echo   Run every 6 hours: python %SCRIPT%
echo.

schtasks /Create /F /SC HOURLY /MO 6 /TN "%TASK_NAME%" ^
  /TR "cmd /c cd /d \"%REPO_DIR%\" && python \"%SCRIPT%\" >> \"%REPO_DIR%\\logs\\law_auto_update.log\" 2>&1"

if errorlevel 1 (
  echo.
  echo Failed to register the task. Try running this .bat as administrator.
  pause
  exit /b 1
)

echo.
echo Done. Verify with:  schtasks /Query /TN %TASK_NAME%
echo Logs append to:    %REPO_DIR%\logs\law_auto_update.log
echo To remove the task: run UNSCHEDULE_LAW_REFRESH.bat
echo.
pause
endlocal

