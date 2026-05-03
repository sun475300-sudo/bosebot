@echo off
REM ============================================================================
REM  bonded-chatbot — merge all 20 sandbox tracks → main, then delete branches.
REM
REM  Run from repo root:
REM      MERGE_ALL_AND_CLEAN.bat
REM
REM  Prerequisites:
REM    1. cd to repo root (the directory containing .git)
REM    2. 'gh' CLI installed and authenticated:    gh auth login
REM    3. 'outputs/pr-artifacts/' contains the bundles + PR_BODY_*.md
REM       (relative to %USERPROFILE%\AppData\Roaming\Claude\... — adjust ART path
REM        below if your artifacts live elsewhere)
REM ============================================================================
setlocal enabledelayedexpansion

REM ----- Configurable paths ---------------------------------------------------
set REPO=%~dp0
set ART=%~dp0outputs\pr-artifacts
if not exist "%ART%\PR_BODY_C.md" (
  REM Try alternate location 1: artifacts copied next to repo
  set ART=%~dp0..\outputs\pr-artifacts
)
if not exist "%ART%\PR_BODY_C.md" (
  echo [ERROR] PR artifacts not found. Edit %~f0 and set ART= to your outputs/pr-artifacts/ path.
  pause
  exit /b 1
)
echo Using artifacts at: %ART%

cd /d "%REPO%"

REM ----- 0. Sanity ------------------------------------------------------------
echo.
echo [0/5] gh CLI auth status
gh auth status 1>nul 2>nul
if errorlevel 1 (
  echo [ERROR] gh CLI not authenticated. Run: gh auth login
  pause
  exit /b 1
)

REM ----- Branch table ---------------------------------------------------------
REM   <Letter> <branch-suffix>
set "B_D=ci-bootstrap-202604280133"
set "B_G=small-fixes-202604280133"
set "B_C=fix-3-audits-202604280103"
set "B_H=perf-stability-cycle3-202604280151"
set "B_J=response-quality-202604280153"
set "B_E=h5-test-isolation-202604280135"
set "B_F=readme-ops-guide-202604280135"
set "B_I=observability-202604280152"
set "B_K=ops-automation-202604280154"
set "B_L=test-strengthen-202604280155"
set "B_M=privacy-202604280158"
set "B_N=backup-restore-202604280200"
set "B_O=per-user-rate-limit-202604280201"
set "B_P=ab-testing-202604280201"
set "B_Q=response-cache-202604280202"
set "B_R=audit-search-api-202604280604"
set "B_S=otel-tracing-202604280606"
set "B_T=lang-detection-202604280606"
set "B_U=anomaly-detection-202604280607"
set "B_V=static-analysis-hardening-202604280608"

REM ----- 1. Sync main ---------------------------------------------------------
echo.
echo [1/5] Sync main
if exist .git\index.lock del /q .git\index.lock
git fetch origin
git checkout main || (echo [ERROR] main checkout failed & pause & exit /b 1)
git pull --ff-only origin main

REM ----- 2. Fetch bundles + push 20 branches in priority order ---------------
echo.
echo [2/5] Fetch + push 20 branches

call :handle D
call :handle G
call :handle C
call :handle H
call :handle J
call :handle E
call :handle F
call :handle I
call :handle K
call :handle L
call :handle M
call :handle N
call :handle O
call :handle P
call :handle Q
call :handle R
call :handle S
call :handle T
call :handle U
call :handle V

goto step3

:handle
set L=%~1
set BR=!B_%L%!
echo   --- %L%  claude/!BR! ---
REM Fetch bundle if local branch missing
git rev-parse --verify "claude/!BR!" 1>nul 2>nul
if errorlevel 1 (
  for %%F in ("%ART%\track-%L%_!BR!.bundle") do (
    if exist "%%F" git fetch "%%F" "claude/!BR!:claude/!BR!" 1>nul 2>nul
  )
)
git push -u origin "claude/!BR!" 2>&1 | findstr /V "Compressing\|Writing\|Total\|remote:" >nul 2>&1
git push -u origin "claude/!BR!"
exit /b 0

:step3
REM ----- 3. Create PRs + auto-merge ------------------------------------------
echo.
echo [3/5] Create PRs + auto-merge (squash)

call :pr_merge D
call :pr_merge G
call :pr_merge C
call :pr_merge H
call :pr_merge J
call :pr_merge E
call :pr_merge F
call :pr_merge I
call :pr_merge K
call :pr_merge L
call :pr_merge M
call :pr_merge N
call :pr_merge O
call :pr_merge P
call :pr_merge Q
call :pr_merge R
call :pr_merge S
call :pr_merge T
call :pr_merge U
call :pr_merge V

goto step4

:pr_merge
set L=%~1
set BR=!B_%L%!
set BODY=%ART%\PR_BODY_%L%.md
echo   --- PR for %L% : claude/!BR! ---

REM Create PR (idempotent — second run errors silently)
gh pr create --base main --head "claude/!BR!" --title "[%L%] auto: claude/!BR!" --body-file "%BODY%" 2>nul

REM Try squash merge (most common). Falls back to merge commit if squash blocked.
gh pr merge "claude/!BR!" --squash --delete-branch 2>nul
if errorlevel 1 (
  gh pr merge "claude/!BR!" --merge --delete-branch 2>nul
  if errorlevel 1 (
    echo     [WARN] %L% merge failed — try manually: gh pr view "claude/!BR!"
  )
)

REM main을 다시 fetch + rebase 로 다음 PR이 깨끗한 baseline을 갖도록 (시퀀셜 머지의 핵심)
git fetch origin >nul 2>&1
git pull --ff-only origin main >nul 2>&1
exit /b 0

:step4
REM ----- 4. Local branch cleanup ----------------------------------------------
echo.
echo [4/5] Local branch cleanup
git checkout main
git pull --ff-only origin main
git remote prune origin
for /f "tokens=*" %%b in ('git for-each-ref --format=%%%(refname:short%%) refs/heads/claude/') do (
  echo   deleting local %%b
  git branch -D "%%b" 1>nul 2>nul
)

REM ----- 5. Final state -------------------------------------------------------
echo.
echo [5/5] Final state
echo --- last 5 commits on main ---
git log --oneline -5
echo.
echo --- local branches (should be only main) ---
git branch
echo.
echo --- still-open PRs ---
gh pr list --state open
echo.
echo === main HEAD ===
git rev-parse HEAD
echo.
echo Done.
pause
exit /b 0
