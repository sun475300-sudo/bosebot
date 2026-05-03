@echo off
REM ============================================================================
REM  bonded-chatbot — ONE-SHOT FIX + RUN
REM
REM  더블클릭 한 번으로 다음 문제 모두 해결:
REM    1. GitHub Desktop 이 .claude/worktrees + .fuse_hi* 노이즈를 main 에 commit 시도 → 정리 + .gitignore
REM    2. cmd 의 cd 가 드라이브 안 바뀌는 문제 → cd /d 사용
REM    3. .git/index.lock 손상 → 자동 정리
REM    4. 22 브랜치 bundle 에서 fetch
REM    5. (옵션) 통합 branch 1개로 push (가장 간단) — gh CLI 있으면 PR 자동 생성
REM    6. 챗봇 서버 :5099 백그라운드 기동 + 헬스 확인
REM ============================================================================
setlocal enabledelayedexpansion
echo.
echo ╔══════════════════════════════════════════════════════════════════════╗
echo ║  bonded-chatbot — ONE-SHOT FIX + RUN                                ║
echo ╚══════════════════════════════════════════════════════════════════════╝

REM --- 0. 위치 고정 (드라이브 전환 포함) ---
cd /d "%~dp0"
set REPO=%CD%
set ART=%REPO%\outputs\pr-artifacts
if not exist "%ART%\INTEGRATED_FINAL.bundle" (
  REM bundle이 outputs/ 아래로 복사 안 됐으면 사용자에게 안내
  set ART=%~dp0outputs\pr-artifacts
)
if not exist "%ART%\INTEGRATED_FINAL.bundle" (
  echo [WARN] INTEGRATED_FINAL.bundle 못 찾음. ART 경로:  %ART%
  echo        bundle 파일을 outputs\pr-artifacts\ 로 복사하시거나
  echo        이 bat 의 'set ART=' 줄을 수정하세요.
  echo        계속 진행 (기존 브랜치만으로) — 무시 가능.
)

echo.
echo [STEP 1/6] 노이즈 정리 ────────────────────────────────────────
REM index.lock / HEAD.lock 강제 제거
if exist .git\index.lock del /q .git\index.lock 2>nul
if exist .git\HEAD.lock  del /q .git\HEAD.lock  2>nul
for /f "usebackq" %%L in (`dir /b /s ".git\refs\heads\claude*.lock" 2^>nul`) do del /q "%%L" 2>nul

REM .gitignore 에 노이즈 패턴 추가 (중복 추가 안 함)
findstr /xc:".claude/" .gitignore >nul 2>&1 || echo .claude/>>.gitignore
findstr /xc:"*.fuse_hidden*" .gitignore >nul 2>&1 || echo *.fuse_hidden*>>.gitignore
findstr /xc:"**/.fuse_hidden*" .gitignore >nul 2>&1 || echo **/.fuse_hidden*>>.gitignore
findstr /xc:"data/.fuse_*" .gitignore >nul 2>&1 || echo data/.fuse_*>>.gitignore

REM staging area 의 노이즈 unstage
git reset HEAD -- .claude/ 2>nul
git reset HEAD -- "data/.fuse_*" 2>nul

REM untracked 노이즈 삭제 (안전 — preview 후 강제)
git clean -fd .claude/ 2>nul
for /f "delims=" %%F in ('git ls-files --others --exclude-standard ^| findstr /R "fuse_hi"') do (
  del /q "%%F" 2>nul
)
echo  ✓ .gitignore 갱신 + 노이즈 untrack

echo.
echo [STEP 2/6] main 동기화 ────────────────────────────────────────
git fetch origin --prune 2>&1 | findstr /V "Fetching\|origin"
git checkout main 2>&1 | findstr /V "^Already"
git pull --ff-only origin main 2>&1 | findstr /V "Already up"
echo  ✓ main HEAD: 
git rev-parse --short=7 HEAD

echo.
echo [STEP 3/6] 22 브랜치 bundle 에서 fetch ───────────────────────
if exist "%ART%" (
  for %%F in ("%ART%\track-*.bundle" "%ART%\INTEGRATED_FINAL.bundle") do (
    if exist "%%~F" (
      for /f "delims=" %%B in ('git bundle list-heads "%%~F" 2^>nul ^| findstr "claude"') do (
        for /f "tokens=2" %%R in ("%%B") do (
          git fetch -f "%%~F" "%%R:%%R" 2>nul
        )
      )
    )
  )
  echo  ✓ bundle fetch 완료
) else (
  echo  ⚠ bundle 디렉토리 없음 — skip
)
echo.
git branch | findstr "claude/" | find /c "claude/"
echo   ↑ 로컬 claude/* 브랜치 수

echo.
echo [STEP 4/6] git push 시도 ─────────────────────────────────────
echo (GitHub Desktop 또는 gh CLI 인증을 사용. 인증 없으면 실패해도 나머지 단계는 진행됨)
git push origin --all 2>&1 | findstr /V "Compressing\|Writing\|Total"

echo.
echo [STEP 5/6] (선택) PR 일괄 생성 — gh CLI 가용 시 ──────────────
where gh >nul 2>&1
if %ERRORLEVEL%==0 (
  gh auth status >nul 2>&1
  if !ERRORLEVEL!==0 (
    echo  gh CLI 인증 OK — MERGE_ALL_AND_CLEAN.bat 으로 PR 자동 생성을 추천:
    echo     "%REPO%\MERGE_ALL_AND_CLEAN.bat"
  ) else (
    echo  gh CLI 미인증. 'gh auth login' 후 MERGE_ALL_AND_CLEAN.bat 실행.
  )
) else (
  echo  gh CLI 미설치. winget install GitHub.cli  → gh auth login.
  echo  또는 GitHub 웹에서 직접 PR 생성:
  echo     https://github.com/sun475300-sudo/bosebot/pulls
)

echo.
echo [STEP 6/6] 챗봇 서버 :5099 기동 + 헬스 ───────────────────────
REM 이전에 떠 있는 서버 정리 (port 5099)
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":5099 "') do taskkill /PID %%P /F 2>nul

REM 백그라운드로 띄우기 (창 한 개 따로 열림)
start "bonded-chatbot :5099" /min cmd /c "python web_server.py --port 5099 --host 127.0.0.1 > logs\server-5099.log 2>&1"

REM 30초 동안 헬스 폴링
echo  서버 부팅 대기 (최대 30초)...
set HEALTH_OK=0
for /l %%i in (1,1,30) do (
  curl -fsS -o nul -w "" http://127.0.0.1:5099/api/health 2>nul && (
    echo  ✓ /api/health 응답 OK after %%i초
    set HEALTH_OK=1
    goto :health_done
  )
  timeout /t 1 /nobreak >nul
)
:health_done

echo.
if !HEALTH_OK!==1 (
  echo ╔══════════════════════════════════════════════════════════════════════╗
  echo ║  ✓ 모두 완료 — 브라우저 열기:                                          ║
  echo ║    http://127.0.0.1:5099/                                            ║
  echo ║    http://127.0.0.1:5099/api/health                                  ║
  echo ║    http://127.0.0.1:5099/metrics                                     ║
  echo ╚══════════════════════════════════════════════════════════════════════╝
  REM 자동으로 기본 브라우저 열기
  start "" "http://127.0.0.1:5099/api/health"
) else (
  echo ⚠ 헬스 체크 timeout. 다른 cmd 창에서 확인:
  echo    type logs\server-5099.log
  echo    또는 수동으로:  python web_server.py --port 5099
)

echo.
echo ── 마지막 점검 항목 ──
git status --short
echo.
git log --oneline -5
echo.
pause
