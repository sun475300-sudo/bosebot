@echo off
REM ============================================================================
REM  bonded-chatbot — cycle 11 (QQ, RR, SS, TT, UU) — push branches & open PRs.
REM  Run from repo root after copying outputs/pr-artifacts/ next to .git
REM ============================================================================
setlocal enabledelayedexpansion

set REPO=%~dp0
set ART=%~dp0outputs\pr-artifacts
if not exist "%ART%\PR_BODY_QQ.md" (
  echo [ERROR] PR_BODY_QQ.md not found at %ART%
  pause
  exit /b 1
)

where gh >nul 2>&1
if errorlevel 1 (
  echo [ERROR] GitHub CLI (gh^) is not installed or not on PATH.
  pause
  exit /b 1
)

call :one QQ track-QQ_webhook-hmac-202605030200          claude/track-QQ-webhook-hmac-202605030200          "feat(webhook): HMAC + timestamp + nonce replay protection (Track QQ)"
call :one RR track-RR_embedding-warmup-202605030210      claude/track-RR-embedding-warmup-202605030210      "feat(perf): FAQ embedding warm-up at boot (Track RR)"
call :one SS track-SS_tenant-rate-limit-202605030220     claude/track-SS-tenant-rate-limit-202605030220     "feat(tenant): per-tenant rate-limit override (Track SS)"
call :one TT track-TT_quality-evaluate-202605030230      claude/track-TT-quality-evaluate-202605030230      "feat(admin): /api/admin/quality/evaluate endpoint (Track TT)"
call :one UU track-UU_csv-validator-202605030240         claude/track-UU-csv-validator-202605030240         "feat(data): CSV schema validator + CI gate (Track UU)"

echo.
echo === Cycle 11: 5 PRs opened. Run MERGE_ALL_AND_CLEAN_CYCLE11.bat to merge. ===
endlocal
exit /b 0

:one
set L=%~1
set BUNDLE=%~2
set BR=%~3
set TITLE=%~4
echo.
echo --- Track %L% ---
git fetch "%ART%\%BUNDLE%.bundle" "%BR%:%BR%"
if errorlevel 1 (
  echo [WARN] bundle fetch failed for %L% — skipping
  goto :eof
)
git push -u origin "%BR%"
if errorlevel 1 (
  echo [WARN] push failed for %L%
  goto :eof
)
gh pr create --base main --head "%BR%" --title "%TITLE%" --body-file "%ART%\PR_BODY_%L%.md"
goto :eof
