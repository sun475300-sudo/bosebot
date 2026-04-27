@echo off
REM =====================================================================
REM Cross-platform local-run helper for Windows.
REM
REM   start.bat                  default port 8080
REM   start.bat --port 5099      custom port
REM
REM Sets up a venv, installs dependencies (only when requirements.txt
REM changes), and runs the dev server. For production / Docker, see
REM docker-compose.yml.
REM =====================================================================
setlocal enabledelayedexpansion

REM Switch to the directory this script lives in (works no matter where it's run from)
cd /d "%~dp0"

REM ---- Check Python ----------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python.exe not found in PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/ and re-run.
    exit /b 1
)

REM ---- Resolve port from CLI / env / default --------------------------
set "PORT=%CHATBOT_PORT%"
if "%PORT%"=="" set "PORT=8080"
set "HOST=%CHATBOT_HOST%"
if "%HOST%"=="" set "HOST=127.0.0.1"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--port" ( set "PORT=%~2" & shift & shift & goto parse_args )
if /I "%~1"=="--host" ( set "HOST=%~2" & shift & shift & goto parse_args )
echo Unknown argument: %~1
exit /b 1
:args_done

REM ---- Create / reuse venv --------------------------------------------
if not exist venv (
    echo Creating virtual environment in .\venv ...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: failed to create venv.
        exit /b 1
    )
)

call venv\Scripts\activate.bat

REM ---- Install deps if requirements.txt changed -----------------------
set "STAMP=venv\.requirements.stamp"
set "REINSTALL=1"
if exist "%STAMP%" (
    for /f %%a in ('powershell -NoProfile -Command "(Get-FileHash requirements.txt -Algorithm SHA256).Hash"') do set "CURHASH=%%a"
    set /p OLDHASH=<"%STAMP%"
    if /I "!CURHASH!"=="!OLDHASH!" set "REINSTALL=0"
)
if "%REINSTALL%"=="1" (
    echo Installing/updating dependencies ...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip install failed.
        exit /b 1
    )
    for /f %%a in ('powershell -NoProfile -Command "(Get-FileHash requirements.txt -Algorithm SHA256).Hash"') do echo %%a> "%STAMP%"
)

if not exist logs mkdir logs

echo ---------------------------------------------------------------
echo  Bonded Exhibition Chatbot
echo  URL:    http://%HOST%:%PORT%
echo  Health: http://%HOST%:%PORT%/api/health
echo  Press Ctrl+C to stop
echo ---------------------------------------------------------------

python web_server.py --host %HOST% --port %PORT%
endlocal
