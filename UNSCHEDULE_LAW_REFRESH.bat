@echo off
REM Unregister the BondedChatbotLawRefresh scheduled task.

setlocal
set TASK_NAME=BondedChatbotLawRefresh

echo Removing scheduled task: %TASK_NAME%
schtasks /Delete /F /TN "%TASK_NAME%"

if errorlevel 1 (
  echo.
  echo Failed to delete the task (it may not be registered, or you may
  echo need administrator rights).
  pause
  exit /b 1
)

echo Done.
pause
endlocal

