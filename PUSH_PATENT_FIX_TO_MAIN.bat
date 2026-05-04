@echo off
REM ========================================================================
REM  [DEPRECATED] PUSH_PATENT_FIX_TO_MAIN.bat
REM
REM  This script is no longer in use.
REM  The patent QA fix it pushed (commits up to fcc3714) is already on
REM  origin/main. Running this script again would create a duplicate
REM  commit or fail with "nothing to commit".
REM
REM  Use PUSH_EVERYTHING_TO_MAIN.bat instead.
REM ========================================================================
echo.
echo [DEPRECATED] PUSH_PATENT_FIX_TO_MAIN.bat is no longer in use.
echo The patent QA fix is already on origin/main (commit fcc3714 and earlier).
echo.
echo Use this single entry-point instead:
echo     PUSH_EVERYTHING_TO_MAIN.bat
echo.
echo See docs\HOW_TO_PUSH.md for the full workflow.
echo.
pause
exit /b 1
