@echo off
REM ========================================================================
REM  PUSH_PATENT_FIX_TO_MAIN.bat
REM  Patent answer-quality fix - commit and push to origin/main
REM
REM  IMPORTANT: Close GitHub Desktop before running this script.
REM  GitHub Desktop holds .git\index.lock and will block git CLI.
REM ========================================================================
chcp 65001 > nul
cd /d E:\GitHub\bonded-exhibition-chatbot-data
echo.
echo === STEP 1: warn user to close GitHub Desktop ===
echo Close GitHub Desktop now if it is open. Press Ctrl+C to abort.
timeout /t 5 > nul
echo.
echo === STEP 2: clean stale lock ===
if exist .git\index.lock (
    echo Removing stale .git\index.lock
    del /f /q .git\index.lock
    if exist .git\index.lock (
        echo [ERROR] cannot remove .git\index.lock - close GitHub Desktop and retry
        pause
        exit /b 1
    )
)
echo.
echo === STEP 3: branch check ===
git rev-parse --abbrev-ref HEAD
git fetch origin
echo.
echo === STEP 4: regression test (must pass before push) ===
python -m pytest tests/test_patent_regression.py -q
if errorlevel 1 (
    echo [ERROR] regression test failed - aborting
    pause
    exit /b 1
)
echo.
echo === STEP 5: unstage everything, then stage ONLY patent fix files ===
git reset
git add .gitignore
git add src/spell_corrector.py
git add src/synonym_resolver.py
git add src/korean_tokenizer.py
git add tests/test_patent_regression.py
git add tests/test_patent_qa_golden.py
echo.
echo === STEP 6: show staged diff summary ===
git diff --cached --stat
echo.
echo === STEP 7: commit ===
git commit -m "fix: bonded-exhibition chatbot - improve patent question answer quality" -m "Bug A: spell_corrector auto-correction mangled procedural words. Added 신청, 지정, 등록, 출원 to KNOWN_TERMS so they survive Levenshtein distance check." -m "Bug B: synonym_resolver single-syllable mappings (사/팔/빼/벌) caused false partial-string matches. Removed 4 mappings; word-level synonyms still apply." -m "Bug C: korean_tokenizer DOMAIN_TERMS missed core patent compounds. Added 특허, 특허기간, 특허신청, 특허장소, 특허취소, 특허연장, 특허신청서, 설치특허, 운영인." -m "Tests: tests/test_patent_regression.py 32 cases + tests/test_patent_qa_golden.py 11 E2E cases. All pass." -m "Also: .claude/ added to .gitignore."
if errorlevel 1 (
    echo [ERROR] commit failed
    pause
    exit /b 1
)
echo.
echo === STEP 8: push to origin/main (no force) ===
git push origin main
if errorlevel 1 (
    echo [ERROR] push failed - check network and credentials
    pause
    exit /b 1
)
echo.
echo [OK] Push complete to origin/main
git log --oneline -3
echo.
pause
