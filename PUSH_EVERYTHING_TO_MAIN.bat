@echo off
REM ========================================================================
REM  PUSH_EVERYTHING_TO_MAIN.bat
REM
REM  Single entry-point: regression tests + commit pending changes + push.
REM  Replaces the old per-feature push scripts (see DEPRECATED .bat files).
REM
REM  Workflow:
REM    1. Unlock repo (delete any stale .git/*.lock from GitHub Desktop)
REM    2. Run the four regression suites that gate every push
REM    3. Stage SAFE files only (no db-journal, *.db.test, bundles, logs)
REM    4. Group remaining changes into clear commits
REM         a) sync_one bug fix (src/law_api_admrul.py + tests)
REM         b) UI readability (web/, docs/UI_READABILITY.md, screenshots)
REM         c) law auto-update (law_auto_updater, law_sync_admin, scheduled)
REM    5. Push origin main (NEVER force)
REM
REM  IMPORTANT: Close GitHub Desktop and any other git client first.
REM             Push is NEVER forced.
REM ========================================================================

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
cd /d "%~dp0"

set REPO_ROOT=%~dp0

echo.
echo ============================================================
echo  PUSH_EVERYTHING_TO_MAIN.bat   (no force push)
echo  Repo: %REPO_ROOT%
echo ============================================================
echo.

REM ------------------------------------------------------------------
REM  STEP 1 / 5  unlock
REM ------------------------------------------------------------------
echo [1/5] Unlocking repo (close GitHub Desktop if open)...
if exist UNLOCK_REPO.bat (
    call UNLOCK_REPO.bat 1>nul 2>nul
) else (
    if exist ".git\index.lock"        del /f /q ".git\index.lock"        2>nul
    if exist ".git\HEAD.lock"         del /f /q ".git\HEAD.lock"         2>nul
    if exist ".git\packed-refs.lock"  del /f /q ".git\packed-refs.lock"  2>nul
    if exist ".git\config.lock"       del /f /q ".git\config.lock"       2>nul
    for /r ".git" %%F in (*.lock) do (del /f /q "%%F" 2>nul)
)
if exist ".git\index.lock" (
    echo [ERROR] .git\index.lock still present. Close GitHub Desktop and retry.
    pause
    exit /b 1
)

git fetch origin 1>nul 2>nul
echo Current branch:
git rev-parse --abbrev-ref HEAD
echo.

REM ------------------------------------------------------------------
REM  STEP 2 / 5  regression
REM ------------------------------------------------------------------
echo [2/5] Running regression tests (must all pass)...
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python is not on PATH.
    pause
    exit /b 1
)

python -m pytest -q ^
    tests\test_law_api_admrul.py ^
    tests\test_bonded_notice_qa.py ^
    tests\test_law_auto_updater.py ^
    tests\test_patent_regression.py ^
    tests\test_chatbot.py
if errorlevel 1 (
    echo.
    echo [ERROR] Regression failed. Aborting commit and push.
    echo         Fix the failing tests, then re-run this script.
    pause
    exit /b 1
)
echo.

REM ------------------------------------------------------------------
REM  STEP 3 / 5  reset and stage SAFE files in groups
REM ------------------------------------------------------------------
echo [3/5] Staging changes (safe files only)...
git reset 1>nul 2>nul

REM ---- group A: sync_one bug fix (admRul HTML fallback hardening) ----
git add src\law_api_admrul.py 2>nul
git add tests\test_law_api_admrul.py 2>nul

REM ---- group B: UI readability pass ----
git add web\index.html 2>nul
git add web\analytics-dashboard.html 2>nul
git add web\admin.html 2>nul
git add web\admin_dashboard.html 2>nul
git add web\faq-manager.html 2>nul
git add web\notifications.html 2>nul
git add web\login.html 2>nul
git add docs\UI_READABILITY.md 2>nul
git add screenshots-final\readability_chatbot_desktop_light.png 2>nul
git add screenshots-final\readability_chatbot_desktop_dark.png 2>nul
git add screenshots-final\readability_chatbot_mobile_light.png 2>nul
git add screenshots-final\readability_analytics_desktop_light.png 2>nul
git add screenshots-final\readability_analytics_desktop_dark.png 2>nul

REM ---- group C: law auto-update background scheduler ----
git add src\law_auto_updater.py 2>nul
git add src\law_sync_admin.py 2>nul
git add scripts\scheduled_refresh.py 2>nul
git add tests\test_law_auto_updater.py 2>nul
git add docs\LAW_AUTO_UPDATE.md 2>nul
git add SCHEDULE_LAW_REFRESH.bat 2>nul
git add UNSCHEDULE_LAW_REFRESH.bat 2>nul

REM ---- group D: docs / deprecated bat housekeeping ----
git add docs\HOW_TO_PUSH.md 2>nul
git add PUSH_EVERYTHING_TO_MAIN.bat 2>nul
git add PUSH_PATENT_FIX_TO_MAIN.bat 2>nul
git add PUSH_LAW_API_TO_MAIN.bat 2>nul
git add README.md 2>nul

REM ---- explicit excludes (never push these) ----
git reset -- "*.db" 2>nul
git reset -- "*.db-journal" 2>nul
git reset -- "*.db.test" 2>nul
git reset -- "*.bundle" 2>nul
git reset -- "logs/*" 2>nul

echo.
echo Staged diff summary:
git diff --cached --stat
echo.

REM ------------------------------------------------------------------
REM  STEP 4 / 5  commit (only if there is staged content)
REM ------------------------------------------------------------------
echo [4/5] Committing staged work...
git diff --cached --quiet
if not errorlevel 1 (
    echo Nothing staged. Skipping commit step.
    goto :push
)

git commit ^
    -m "chore(release): unified push - sync_one fix + UI + auto-update + docs" ^
    -m "Bug fix: src/law_api_admrul.py sync_one HTML fallback now treats" ^
    -m "  short or article-less results as fetch_failed and preserves the" ^
    -m "  prior cache instead of overwriting it with 55-byte meta text." ^
    -m "  New status no_credentials separates blank LAW_API_OC case." ^
    -m "Tests: 5 new regression cases in tests/test_law_api_admrul.py" ^
    -m "  (empty html, short html, preserves prior cache, big html ok)." ^
    -m "Ops: PUSH_EVERYTHING_TO_MAIN.bat is now the single push entrypoint." ^
    -m "  PUSH_PATENT_FIX_TO_MAIN.bat / PUSH_LAW_API_TO_MAIN.bat marked DEPRECATED." ^
    -m "Docs: docs/HOW_TO_PUSH.md explains which script to run when."
if errorlevel 1 (
    echo [WARN] git commit returned non-zero. May simply be 'nothing to commit'.
)

:push
REM ------------------------------------------------------------------
REM  STEP 5 / 5  push origin main (NEVER force)
REM ------------------------------------------------------------------
echo.
echo [5/5] Pushing to origin/main (NO force)...
git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] git push failed. Common causes:
    echo   - origin/main has commits you do not have:
    echo       git pull --ff-only origin main
    echo       (resolve, re-run regression, re-run this script)
    echo   - Bad credentials: open Windows Credential Manager and remove
    echo       any stale github.com entry, then retry.
    pause
    exit /b 1
)

echo.
echo === DONE. Latest commit: ===
git log --oneline -1
echo.
echo Remote main: 
git rev-parse origin/main
echo.

pause
endlocal
exit /b 0
