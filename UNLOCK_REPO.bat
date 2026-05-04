@echo off
REM ============================================================
REM UNLOCK_REPO.bat
REM Removes git lock files that block GitHub Desktop / git CLI.
REM Safe to run multiple times. Double-click to use.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo === Removing all .lock files under .git ===
echo.

REM Common top-level locks
if exist ".git\index.lock"        del /f /q ".git\index.lock"        2>nul && echo  - removed .git\index.lock
if exist ".git\HEAD.lock"         del /f /q ".git\HEAD.lock"         2>nul && echo  - removed .git\HEAD.lock
if exist ".git\packed-refs.lock"  del /f /q ".git\packed-refs.lock"  2>nul && echo  - removed .git\packed-refs.lock
if exist ".git\config.lock"       del /f /q ".git\config.lock"       2>nul && echo  - removed .git\config.lock
if exist ".git\shallow.lock"      del /f /q ".git\shallow.lock"      2>nul && echo  - removed .git\shallow.lock
if exist ".git\gc.pid"            del /f /q ".git\gc.pid"            2>nul && echo  - removed .git\gc.pid
if exist ".git\objects\maintenance.lock" del /f /q ".git\objects\maintenance.lock" 2>nul && echo  - removed .git\objects\maintenance.lock

REM Sweep the rest (refs/heads/*.lock, refs/remotes/*.lock, etc.)
for /r ".git" %%F in (*.lock) do (
    del /f /q "%%F" 2>nul && echo  - removed %%F
)

echo.
echo === Verifying repository ===
echo.
git status --short
if errorlevel 1 (
    echo.
    echo [WARN] git status failed. The repo may still be busy.
    echo        Close GitHub Desktop and try this script again.
    goto :end
)

echo.
echo === Running git fsck ===
git fsck --no-dangling

echo.
echo === Done. You can now use GitHub Desktop again. ===
echo.

:end
pause
endlocal
