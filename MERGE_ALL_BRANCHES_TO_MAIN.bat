@echo off
REM ========================================================================
REM  MERGE_ALL_BRANCHES_TO_MAIN.bat (ASCII-only)
REM  Safely merge 35+ cycle branches into main - guided script
REM
REM  Usage:
REM    1) PUSH_PATENT_FIX_TO_MAIN.bat must succeed first
REM    2) This script asks confirmation per STEP
REM ========================================================================
cd /d E:\GitHub\bonded-exhibition-chatbot-data
if errorlevel 1 (
    echo [ERROR] cd failed - check path
    pause
    exit /b 1
)

echo.
echo === Pre-check ===
git rev-parse --abbrev-ref HEAD
git status --short | findstr /v fuse_hidden

echo.
echo === STEP 1: cleanup already-merged branches ===
echo (branches already in main can be safely deleted)
echo.
set /p ANS=Proceed delete? (y/n) :
if /i "%ANS%"=="y" (
    git branch -d claude/angry-dirac-f983f1 2>nul
    git branch -d claude/relaxed-hoover-bcde14 2>nul
    git branch -d claude/ui-polish-20260428-085757 2>nul
)

echo.
echo === STEP 2: merge CLEAN group (6 branches) ===
echo (no conflict expected, --no-ff)
echo.
set /p ANS=Merge CLEAN group? (y/n) :
if /i "%ANS%"=="y" (
    for %%B in (
        claude/cross-platform-setup-20260428-085238
        claude/cross-platform-setup-20260428085407
        claude/fix-bot-startup-deps
        claude/track-CC-websocket-202605030001
        claude/track-EE-feedback-loop-202605030010
        claude/ui-polish-20260428085407
    ) do (
        echo --- merging %%B ---
        git merge --no-ff -m "merge: %%B" %%B
        if errorlevel 1 (
            echo [STOP] %%B merge failed - resolve manually then rerun
            pause
            exit /b 1
        )
        python -m pytest tests/test_patent_regression.py -q
        if errorlevel 1 (
            echo [STOP] regression failed - consider reverting merge
            pause
            exit /b 1
        )
    )
    git push origin main
    if errorlevel 1 (
        echo [ERROR] push failed
        pause
        exit /b 1
    )
)

echo.
echo === STEP 3: CONFLICT group (10 branches) - manual handling ===
echo The following branches may conflict, handle one by one:
echo   claude/master-plan-bonded            (ahead=4)   smallest
echo   claude/fix-tests-ci-green            (ahead=8)
echo   claude/fix-vector-search-w293        (ahead=9)
echo   claude/phase5-ops-202604271300       (ahead=10)
echo   claude/phase7-tests-202604271400     (ahead=13)
echo   claude/fix-ui-scroll-202604271500    (ahead=14)
echo   claude/perf-stability-202604271200   (ahead=14)
echo   claude/fix-ui-sidebar-202604271600   (ahead=15)
echo   claude/fix-jwt-cors-202604271700     (ahead=16)
echo   claude/h4-st-fixture-mock-202604271800 (ahead=17)
echo.
echo Procedure (per branch):
echo   git checkout BRANCH_NAME
echo   git rebase main
echo   (resolve conflicts) git rebase --continue
echo   git checkout main
echo   git merge --no-ff BRANCH_NAME
echo   python -m pytest tests/test_patent_regression.py
echo   git push origin main
echo.
pause
