@echo off
REM ============================================================
REM COMMIT_UI_READABILITY.bat
REM 가독성 패스 (web/, docs/UI_READABILITY.md, screenshots-final/)
REM 만 main 에 커밋하고 push 합니다. force push 안 함.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo === 1) git lock 정리 ===
if exist ".git\index.lock" del /f /q ".git\index.lock" 2>nul
if exist ".git\HEAD.lock"  del /f /q ".git\HEAD.lock"  2>nul
for /r ".git" %%F in (*.lock) do del /f /q "%%F" 2>nul

echo.
echo === 2) 현재 브랜치 확인 ===
git branch --show-current
if errorlevel 1 goto :fail

echo.
echo === 3) UI 가독성 변경분만 stage ===
git add web/index.html ^
        web/analytics-dashboard.html ^
        web/admin.html ^
        web/admin_dashboard.html ^
        web/faq-manager.html ^
        web/notifications.html ^
        web/login.html ^
        docs/UI_READABILITY.md ^
        screenshots-final/readability_chatbot_desktop_light.png ^
        screenshots-final/readability_chatbot_desktop_dark.png ^
        screenshots-final/readability_chatbot_mobile_light.png ^
        screenshots-final/readability_analytics_desktop_light.png ^
        screenshots-final/readability_analytics_desktop_dark.png
if errorlevel 1 goto :fail

echo.
echo === 4) staged diff 요약 ===
git diff --cached --stat

echo.
echo === 5) commit ===
git commit -m "feat(ui): readability pass — low-saturation tokens, Pretendard, WCAG AA" ^
           -m "- chatbot index.html: solid panels, 72ch content max, legal-ref left-stripe, prefers-color-scheme auto" ^
           -m "- analytics-dashboard: softer chart palette, sticky table head, dark heatmap interpolation" ^
           -m "- admin/faq/notifications: readability overlay (chart fills, badges, tables)" ^
           -m "- login: token-driven design with light/dark auto" ^
           -m "- WCAG: dark user bubble 3.66 -> 4.63, light meta 2.85 -> 6.39 (FAIL -> AA)" ^
           -m "- screenshots: screenshots-final/readability_*.png" ^
           -m "- docs: docs/UI_READABILITY.md"
if errorlevel 1 goto :fail

echo.
echo === 6) push to origin/main (NO force) ===
git push origin main
if errorlevel 1 (
    echo.
    echo [WARN] push 실패. 원격이 앞서 있을 수 있습니다. 수동으로 pull --rebase 후 다시 시도하세요.
    goto :end
)

echo.
echo === Done. ===

:end
pause
exit /b 0

:fail
echo.
echo [ERROR] 단계 실패. 위 메시지를 확인하세요.
pause
exit /b 1
