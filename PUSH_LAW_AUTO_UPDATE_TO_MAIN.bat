@echo off
REM ========================================================================
REM  PUSH_LAW_AUTO_UPDATE_TO_MAIN.bat
REM  Commit and push the law/admRul auto-update background scheduler.
REM
REM  Adds:
REM    - src/law_auto_updater.py        background scheduler
REM    - src/law_sync_admin.py          admin Flask routes
REM    - scripts/scheduled_refresh.py   external (Task Scheduler) entry
REM    - SCHEDULE_LAW_REFRESH.bat       register schtasks job
REM    - UNSCHEDULE_LAW_REFRESH.bat     remove schtasks job
REM    - tests/test_law_auto_updater.py 8 unit tests
REM    - docs/LAW_AUTO_UPDATE.md        ops guide
REM    - src/chatbot.py  (modified)     refresh + enable hooks + _get_category_name
REM    - README.md       (modified)     doc pointer
REM
REM  IMPORTANT: Close GitHub Desktop and any other git client first.
REM  They hold .git/index.lock which blocks git add.
REM  Push is NEVER forced. Tests must pass.
REM ========================================================================

setlocal
cd /d "%~dp0"

REM --- 0. Remove stale index.lock (left by GitHub Desktop / crashed git) -
if exist ".git\index.lock" (
  echo Removing stale .git\index.lock ...
  del /f /q ".git\index.lock"
  if exist ".git\index.lock" (
    echo ERROR: Could not remove .git\index.lock.
    echo Close GitHub Desktop / VS Code Git pane and try again.
    pause
    exit /b 1
  )
)

REM --- 1. Run the test gate ----------------------------------------------
echo.
echo [1/4] Running regression: law_auto_updater + admrul + bonded_notice + chatbot
where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: python not on PATH.
  pause
  exit /b 1
)
python -m pytest -q tests/test_law_auto_updater.py tests/test_law_api_admrul.py tests/test_bonded_notice_qa.py tests/test_chatbot.py
if errorlevel 1 (
  echo ERROR: tests failed. Aborting commit.
  pause
  exit /b 1
)

REM --- 2. Stage targeted files only --------------------------------------
echo.
echo [2/4] git add (targeted)
git add ^
  src/law_auto_updater.py ^
  src/law_sync_admin.py ^
  scripts/scheduled_refresh.py ^
  SCHEDULE_LAW_REFRESH.bat ^
  UNSCHEDULE_LAW_REFRESH.bat ^
  tests/test_law_auto_updater.py ^
  docs/LAW_AUTO_UPDATE.md ^
  src/chatbot.py ^
  README.md
if errorlevel 1 (
  echo ERROR: git add failed.
  pause
  exit /b 1
)

REM --- 3. Commit ---------------------------------------------------------
echo.
echo [3/4] git commit
git commit -m "feat(law): in-app + Task Scheduler auto-update for admRul/law" -m "- LawAutoUpdater daemon thread (LAW_AUTO_UPDATE_ENABLED, INTERVAL_HOURS, INITIAL_DELAY)" -m "- on_change rebuilds admrul_index live (no restart)" -m "- /api/admin/law-sync/status + /refresh routes (Bearer ADMIN_TOKEN)" -m "- scheduled_refresh.py + SCHEDULE/UNSCHEDULE_LAW_REFRESH.bat (schtasks)" -m "- 8 new tests, docs/LAW_AUTO_UPDATE.md" -m "- restore _get_category_name on BondedExhibitionChatbot (test_chatbot regression)"
if errorlevel 1 (
  echo NOTE: git commit returned non-zero. May be "nothing to commit".
  echo Continuing to push step.
)

REM --- 4. Push to main (NEVER force) -------------------------------------
echo.
echo [4/4] git push origin main
git push origin main
if errorlevel 1 (
  echo.
  echo ERROR: git push failed. Most common reasons:
  echo   - main has remote changes  -^>  run:  git pull --ff-only origin main
  echo   - bad credentials          -^>  open Windows Credential Manager and
  echo                                  remove old github.com entries, then retry
  pause
  exit /b 1
)

echo.
echo SUCCESS. Latest commit:
git log --oneline -1
echo.
pause
endlocal

