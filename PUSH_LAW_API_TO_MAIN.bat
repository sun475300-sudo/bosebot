@echo off
REM ========================================================================
REM  [DEPRECATED] PUSH_LAW_API_TO_MAIN.bat
REM
REM  This script is no longer in use.
REM  The admRul fetcher work it pushed is already on origin/main as
REM  commit fcc3714 ("feat(bonded): admRul wiring + ops bat scripts ...").
REM  Running it again would conflict with later work.
REM
REM  Use PUSH_EVERYTHING_TO_MAIN.bat instead.
REM ========================================================================
echo.
echo [DEPRECATED] PUSH_LAW_API_TO_MAIN.bat is no longer in use.
echo The admRul fetcher (admRulSeq=2100000276240) is already on origin/main
echo (commit fcc3714).
echo.
echo Use this single entry-point instead:
echo     PUSH_EVERYTHING_TO_MAIN.bat
echo.
echo See docs\HOW_TO_PUSH.md for the full workflow.
echo.
pause
exit /b 1
