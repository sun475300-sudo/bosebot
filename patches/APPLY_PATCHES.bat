@echo off
REM ════════════════════════════════════════════════════════════════════════
REM  bonded-chatbot — apply 3 fix patches + run new tests
REM  더블클릭 또는 cmd에서 한 번 실행 → 끝.
REM ════════════════════════════════════════════════════════════════════════
setlocal
cd /d %~dp0..
echo.
echo ── checking patches against current branch ──
git apply --check patches/0001-session-auto-create.patch || (echo [FAIL] 0001 conflict & pause & exit /b 1)
git apply --check patches/0002-brute-force-lockout.patch || (echo [FAIL] 0002 conflict & pause & exit /b 1)
git apply --check patches/0003-rate-limit-env.patch       || (echo [FAIL] 0003 conflict & pause & exit /b 1)
echo all 3 patches OK to apply.
echo.
echo ── applying ──
git apply patches/0001-session-auto-create.patch && echo  [✓] 0001 session-auto-create
git apply patches/0002-brute-force-lockout.patch && echo  [✓] 0002 brute-force-lockout
git apply patches/0003-rate-limit-env.patch       && echo  [✓] 0003 rate-limit-env
echo.
echo ── running 13 new tests ──
python -m pytest tests\test_session_auto_create.py tests\test_auth_lockout.py tests\test_rate_limit_env.py -v
echo.
echo ── status ──
git status --short
echo.
echo Done. Review with: git diff
echo Commit with:       git add -A ^&^& git commit -m "fix: apply 3 audit patches"
pause
