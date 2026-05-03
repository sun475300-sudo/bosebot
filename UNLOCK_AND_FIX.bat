@echo off
REM ============================================================================
REM  bonded-chatbot — UNLOCK + FIX (GitHub Desktop "Commit failed" 해결)
REM
REM  관리자 권한으로 실행 권장 (마우스 우클릭 → "관리자 권한으로 실행")
REM  이유: WSL/FUSE 가 잡고 있는 .git/index.lock 을 강제로 풀려면
REM        Windows 쪽 권한이 필요할 수 있음
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo.
echo === bonded-chatbot UNLOCK + FIX ===
echo.

REM --- 1. GitHub Desktop 종료 (lock 잡고 있을 수 있음) ---
echo [1/7] GitHub Desktop 종료
taskkill /IM GitHubDesktop.exe /F 2>nul
taskkill /IM "GitHub Desktop.exe" /F 2>nul

REM --- 2. WSL/FUSE 프로세스 종료 (FUSE hidden 파일 원인) ---
echo [2/7] WSL/FUSE 정리
wsl --shutdown 2>nul

REM 3초 대기 — WSL 종료 후 FUSE 핸들 해제
timeout /t 3 /nobreak >nul

REM --- 3. lock 파일 강제 삭제 ---
echo [3/7] .git lock 파일 강제 삭제
del /F /Q .git\index.lock 2>nul && echo   ✓ index.lock 삭제 || echo   ✓ index.lock 없음 또는 이미 삭제됨
del /F /Q .git\HEAD.lock 2>nul && echo   ✓ HEAD.lock 삭제 || echo   - HEAD.lock 없음
del /F /Q .git\config.lock 2>nul
for /f "delims=" %%L in ('dir /s /b .git\refs\*.lock 2^>nul') do (
  del /F /Q "%%L" 2>nul && echo   ✓ deleted %%L
)

REM --- 4. .gitignore 갱신 (노이즈 영구 제외) ---
echo [4/7] .gitignore 갱신
findstr /xc:".claude/" .gitignore >nul 2>&1 || echo .claude/>>.gitignore
findstr /xc:"*.fuse_hidden*" .gitignore >nul 2>&1 || echo *.fuse_hidden*>>.gitignore
findstr /xc:"**/.fuse_hidden*" .gitignore >nul 2>&1 || echo **/.fuse_hidden*>>.gitignore
findstr /xc:"data/.fuse_*" .gitignore >nul 2>&1 || echo data/.fuse_*>>.gitignore
findstr /xc:"data/*.fuse_*" .gitignore >nul 2>&1 || echo data/*.fuse_*>>.gitignore
echo   ✓ .gitignore 패턴 추가됨

REM --- 5. staged 노이즈 unstage + 작업트리 노이즈 삭제 ---
echo [5/7] 노이즈 파일 정리
git status >nul 2>&1
if errorlevel 1 (
  echo   [WARN] git status 실패 — repo 손상 가능. .git 디렉토리 권한 확인 필요.
  goto step6
)
git reset HEAD -- ".claude/" 2>nul
git reset HEAD -- "data/.fuse_*" 2>nul
git checkout -- .gitignore 2>nul
git add .gitignore

REM untracked 노이즈 삭제
for /f "delims=" %%F in ('git ls-files --others --exclude-standard 2^>nul ^| findstr "fuse_hi"') do (
  del /F /Q "%%F" 2>nul
)
rmdir /s /q .claude\worktrees 2>nul
echo   ✓ untracked 노이즈 삭제

:step6
REM --- 6. .gitignore 단독 commit (다른 파일 안 건드림) ---
echo [6/7] .gitignore commit
git -c user.email=user@local -c user.name=user commit -q -m "chore(gitignore): exclude .claude worktrees and FUSE temp files" .gitignore 2>&1 | findstr /V "^$"

REM --- 7. 상태 출력 ---
echo [7/7] 최종 상태
echo.
echo --- git status ---
git status --short
echo.
echo --- 최근 commit 5개 ---
git log --oneline -5
echo.
echo === 완료 ===
echo.
echo 다음 단계:
echo   1. GitHub Desktop 다시 열어서 'Pending changes' 가 거의 비어있는지 확인
echo   2. main 브랜치 그대로 두고, 사이클 1~6 작업은 MERGE_ALL_AND_CLEAN.bat 으로 처리
echo.
pause
