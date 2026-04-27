@echo off
echo MARKER %DATE% %TIME% > "%~dp0bat_marker.txt"
where powershell >> "%~dp0bat_marker.txt" 2>&1
where git >> "%~dp0bat_marker.txt" 2>&1
echo --- running script --- >> "%~dp0bat_marker.txt"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cleanup_safe_branches.ps1" >> "%~dp0bat_marker.txt" 2>&1
echo PS_EXIT=%ERRORLEVEL% >> "%~dp0bat_marker.txt"
echo BAT_DONE %DATE% %TIME% >> "%~dp0bat_marker.txt"
