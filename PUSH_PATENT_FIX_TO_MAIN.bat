@echo off
REM ========================================================================
REM  PUSH_PATENT_FIX_TO_MAIN.bat
REM  보세 전시장 챗봇 - 특허 답변 품질 수정 main 푸시
REM  
REM  변경 파일:
REM    - src/spell_corrector.py     : KNOWN_TERMS에 신청/지정/등록/출원 추가
REM    - src/synonym_resolver.py    : 단일음절 매핑 제거 (사/팔/빼/벌)
REM    - src/korean_tokenizer.py    : DOMAIN_TERMS에 특허 복합명사 추가
REM    - tests/test_patent_regression.py : 32건 회귀 테스트 추가
REM ========================================================================
chcp 65001 > nul
cd /d E:\GitHub\bonded-exhibition-chatbot-data
echo.
echo === STEP 1: stale lock file cleanup ===
if exist .git\index.lock (
    echo Removing stale .git\index.lock
    del /f /q .git\index.lock
)
echo.
echo === STEP 2: current branch check ===
git rev-parse --abbrev-ref HEAD
git status --short
echo.
echo === STEP 3: regression test (must pass) ===
python -m pytest tests/test_patent_regression.py -q
if errorlevel 1 (
    echo.
    echo [ERROR] regression test failed - push aborted
    pause
    exit /b 1
)
echo.
echo === STEP 4: stage only patent fix files ===
git add src/spell_corrector.py src/synonym_resolver.py src/korean_tokenizer.py tests/test_patent_regression.py
git status --short
echo.
echo === STEP 5: commit ===
git commit -m "fix: 보세 전시장 특허 질문 답변 품질 개선 (retrieval/tokenizer/spell)" -m "BUG A: spell_corrector가 신청/지정 등을 신고/규정으로 자동 변환하던 문제 해결 - KNOWN_TERMS에 신청, 지정, 등록, 출원 추가" -m "BUG B: synonym_resolver의 단일 음절 매핑(사/팔/빼/벌)이 부분 문자열 매치로 오작동하던 문제 해결 - 4개 매핑 제거" -m "BUG C: korean_tokenizer DOMAIN_TERMS에 특허 핵심 복합명사 누락 - 특허, 특허기간, 특허신청, 특허장소, 특허취소, 특허연장, 특허신청서, 설치특허, 운영인 추가" -m "tests: tests/test_patent_regression.py 32 cases (12 골든 카테고리 라우팅 + 20 단위 테스트)"
if errorlevel 1 (
    echo.
    echo [ERROR] commit failed - push aborted
    pause
    exit /b 1
)
echo.
echo === STEP 6: push to origin/main (no force) ===
git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] push failed - check network and credentials
    pause
    exit /b 1
)
echo.
echo === DONE ===
git log --oneline -3
echo.
pause
