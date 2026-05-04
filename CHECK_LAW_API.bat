@echo off
REM ============================================================
REM   CHECK_LAW_API.bat
REM   law.go.kr admRul Open API live diagnostic
REM   Target: admRulSeq=2100000276240 (Customs notice)
REM ============================================================
chcp 65001 > nul
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo.
echo ============================================================
echo   1) Environment
echo ============================================================
where python > nul 2>&1
if errorlevel 1 (
  echo [ERROR] python not on PATH. Activate your venv first.
  goto :end
)
python --version
echo LAW_API_OC = [%LAW_API_OC%]
if "%LAW_API_OC%"=="" (
  if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
      if /i "%%A"=="LAW_API_OC" set "LAW_API_OC=%%B"
    )
    echo .env loaded LAW_API_OC = [!LAW_API_OC!]
  ) else (
    echo [WARN] no .env, no LAW_API_OC env var
  )
)

echo.
echo ============================================================
echo   2) HTML viewer (no auth required)
echo ============================================================
python -c "import urllib.request as u; r=u.urlopen(u.Request('https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000276240', headers={'User-Agent':'Mozilla/5.0'}), timeout=15); b=r.read().decode('utf-8','replace'); print('STATUS', r.status, 'len', len(b)); print('HAS_TITLE',     '\xeb\xb3\xb4\xec\x84\xb8\xec\xa0\x84\xec\x8b\x9c\xec\x9e\xa5' in b)"
if errorlevel 1 echo [ERROR] HTML viewer fetch failed.

echo.
echo ============================================================
echo   3) XML Open API (OC required)
echo ============================================================
python -c "import os, urllib.request as u; oc=os.environ.get('LAW_API_OC',''); url=f'https://www.law.go.kr/DRF/lawService.do?OC={oc}&target=admrul&type=XML&ID=2100000276240'; print('URL=', url[:90]+('...' if len(url)>90 else '')); r=u.urlopen(u.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=20); b=r.read().decode('utf-8','replace'); print('STATUS', r.status, 'len', len(b)); print(b[:500])"
if errorlevel 1 echo [ERROR] XML API fetch failed.

echo.
echo ============================================================
echo   4) AdmRulSyncManager.sync_one (writes to data/law_sync.db)
echo ============================================================
python -c "import sys; sys.path.insert(0,'.'); from src.law_api_admrul import AdmRulSyncManager; m=AdmRulSyncManager(); s=m.sync_one('2100000276240'); print('status =', s); c=m.get_cached('2100000276240') or {}; arts=c.get('articles') or {}; print('cached.name =', c.get('name','')); print('cached.agency =', c.get('agency','')); print('cached.eff_date =', c.get('effective_date','')); print('cached.article_count =', len(arts)); print('cached.article_keys =', list(arts.keys())[:10])"
if errorlevel 1 echo [ERROR] sync_one failed.

echo.
echo ============================================================
echo   5) Pytest integration (only if RUN_LAW_API_INTEGRATION=1)
echo ============================================================
set RUN_LAW_API_INTEGRATION=1
python -m pytest tests/test_law_api_admrul.py -k "integration or live" -v --no-header
set RUN_LAW_API_INTEGRATION=

echo.
echo ============================================================
echo   DONE
echo ============================================================
echo If section 3 body shows "missing required parameter" message:
echo   -^> OC key is required. Apply at:
echo      https://open.law.go.kr/LSO/openApi/cuAskList.do
echo   -^> Then add LAW_API_OC=your_email_id to .env
echo.
:end
pause
endlocal