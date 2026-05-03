@echo off
REM ========================================================================
REM  MERGE_ALL_BRANCHES_TO_MAIN.bat
REM  35+ cycle 브랜치를 main으로 안전하게 병합 - 안내 스크립트
REM  
REM  사용법:
REM    1) PUSH_PATENT_FIX_TO_MAIN.bat 가 먼저 성공해야 함
REM    2) 본 스크립트는 STEP 단위로 사용자에게 확인 받으며 진행
REM ========================================================================
chcp 65001 > nul
cd /d E:\GitHub\bonded-exhibition-chatbot-data
echo.
echo === 사전 점검 ===
git rev-parse --abbrev-ref HEAD
git status --short | findstr /v fuse_hidden
echo.
echo === STEP 1: 이미 머지된 브랜치 정리 ===
echo (이미 main에 포함된 브랜치는 안전하게 삭제 가능)
echo.
set /p ANS=삭제 진행? (y/n) :
if /i "%ANS%"=="y" (
    git branch -d claude/angry-dirac-f983f1 2>nul
    git branch -d claude/relaxed-hoover-bcde14 2>nul
    git branch -d claude/ui-polish-20260428-085757 2>nul
)
echo.
echo === STEP 2: CLEAN 그룹 머지 (6개) ===
echo (충돌 없음, --no-ff)
echo.
set /p ANS=CLEAN 그룹 머지? (y/n) :
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
            echo [STOP] %%B 에서 실패 - 수동 해결 후 재실행
            pause
            exit /b 1
        )
        python -m pytest tests/test_patent_regression.py -q
        if errorlevel 1 (
            echo [STOP] regression 실패 - 머지 되돌리기 권장
            pause
            exit /b 1
        )
    )
    git push origin main
)
echo.
echo === STEP 3: CONFLICT 그룹 (10개) - 수동 처리 안내 ===
echo 다음 브랜치들은 충돌 가능성이 있어 수동으로 처리:
echo   claude/master-plan-bonded            (ahead=4)   ← 가장 작음
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
echo 처리 절차 (한 브랜치씩):
echo   git checkout BRANCH_NAME
echo   git rebase main
echo   (충돌 해결 후) git rebase --continue
echo   git checkout main
echo   git merge --no-ff BRANCH_NAME
echo   python -m pytest tests/test_patent_regression.py
echo   git push origin main
echo.
pause
