@echo off
REM ════════════════════════════════════════════════════════════════════
REM  보세전시장 챗봇 — UI 폴리시 Before/After 스크린샷 5장 한 번에 열기
REM  더블클릭하면 기본 이미지 뷰어로 5장 모두 자동 표시됩니다.
REM ════════════════════════════════════════════════════════════════════
cd /d %~dp0
echo Opening 5 screenshots from screenshots-final\ ...
start "" "screenshots-final\before_desktop.png"
start "" "screenshots-final\before_mobile.png"
start "" "screenshots-final\after_desktop.png"
start "" "screenshots-final\after_desktop_dark.png"
start "" "screenshots-final\after_mobile.png"
echo Done. (5 images launched)
