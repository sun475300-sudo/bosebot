@echo off
REM ========================================================================
REM  PUSH_LAW_API_TO_MAIN.bat
REM  Commit and push admRul (administrative rule) fetcher work to origin/main.
REM
REM  Adds:
REM    - src/law_api_admrul.py             admRul Open API client + cache
REM    - src/chatbot.py                    admrul_index integration
REM    - tests/test_law_api_admrul.py      unit tests (mocked HTTP)
REM    - tests/test_bonded_notice_qa.py    bosejeonsijang notice golden set
REM    - scripts/refresh_law_data.py       law + admRul refresher
REM    - REFRESH_LAW_DATA.bat              user-facing refresher
REM    - data/legal_references.json        admRulSeq=2100000276240 update
REM
REM  IMPORTANT: Close GitHub Desktop before running. It holds index.lock.
REM  Push is NEVER forced. Regression must pass before push.
REM ========================================================================
chcp 65001 > nul
cd /d E:\GitHub\bonded-exhibition-chatbot-data
echo.
echo === STEP 1: warn user to close GitHub Desktop ===
echo Close GitHub Desktop now if it is open. Press Ctrl+C to abort.
timeout /t 5 > nul
echo.
echo === STEP 2: clean stale locks ===
call UNLOCK_REPO.bat
if exist .git\index.lock (
    echo [ERROR] .git\index.lock still present - close GitHub Desktop and retry
    pause
    exit /b 1
)
echo.
echo === STEP 3: branch check ===
git rev-parse --abbrev-ref HEAD
git fetch origin
echo.
echo === STEP 4: regression test (must pass before push) ===
python -m pytest tests/test_law_api_admrul.py tests/test_bonded_notice_qa.py tests/test_law_api_sync.py tests/test_patent_regression.py tests/test_chatbot.py -q
if errorlevel 1 (
    echo [ERROR] regression test failed - aborting push
    pause
    exit /b 1
)
echo.
echo === STEP 5: unstage everything, then stage ONLY admRul work files ===
git reset
git add src/law_api_admrul.py
git add src/chatbot.py
git add tests/test_law_api_admrul.py
git add tests/test_bonded_notice_qa.py
git add scripts/refresh_law_data.py
git add REFRESH_LAW_DATA.bat
git add data/legal_references.json
git add .env.example
git add Makefile
echo.
echo === STEP 6: show staged diff summary ===
git diff --cached --stat
if errorlevel 1 (
    echo [ERROR] git diff failed
    pause
    exit /b 1
)
echo.
echo === STEP 7: commit ===
git commit -m "feat: add admRul fetcher for bosejeonsijang notice (admRulSeq=2100000276240)" -m "- New AdmRulAPIClient + AdmRulSyncManager in src/law_api_admrul.py" -m "- SQLite cache: admrul_content_cache, admrul_sync_log" -m "- Chatbot integrates admrul_index with keyword fallback" -m "- legal_references.json updated to latest admRulSeq" -m "- scripts/refresh_law_data.py + REFRESH_LAW_DATA.bat for user refresh"
if errorlevel 1 (
    echo [WARN] nothing to commit OR commit failed
    pause
    exit /b 1
)
echo.
echo === STEP 8: push to origin/main (NO force) ===
git push origin main
if errorlevel 1 (
    echo [ERROR] push failed - run UNLOCK_REPO.bat and retry
    pause
    exit /b 1
)
echo.
echo === DONE: admRul fetcher pushed to origin/main ===
echo.
pause
