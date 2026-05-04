@echo off
REM ============================================================================
REM  bonded-chatbot — cycle 11 — merge 5 sandbox tracks (QQ, RR, SS, TT, UU)
REM                  into main, then delete the local + remote branches.
REM
REM  Run from repo root AFTER PUSH_ALL_CYCLE11.bat has opened the PRs.
REM
REM  Safety: --squash --auto --delete-branch.  No --admin, no force-push.
REM ============================================================================
setlocal enabledelayedexpansion

set REPO=%~dp0
where gh >nul 2>&1
if errorlevel 1 (
  echo [ERROR] GitHub CLI (gh^) is not installed or not on PATH.
  pause
  exit /b 1
)

call :merge claude/track-QQ-webhook-hmac-202605030200
call :merge claude/track-RR-embedding-warmup-202605030210
call :merge claude/track-SS-tenant-rate-limit-202605030220
call :merge claude/track-TT-quality-evaluate-202605030230
call :merge claude/track-UU-csv-validator-202605030240

echo.
echo === Cycle 11: requested squash-merges queued. Check `gh pr list` for state. ===
endlocal
exit /b 0

:merge
set BR=%~1
echo.
echo --- Merging %BR% (squash, auto, delete-branch) ---
gh pr merge "%BR%" --squash --auto --delete-branch
if errorlevel 1 (
  echo [WARN] gh pr merge failed for %BR% (no open PR?  Check `gh pr list`)
)
goto :eof
