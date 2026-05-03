@echo off
REM ========================================================================
REM  PUSH_PATENT_FIX_TO_MAIN.bat (ASCII-only)
REM  Bonded exhibition chatbot - patent answer quality fix push to main
REM
REM  Changed files:
REM    - src/spell_corrector.py     : add KNOWN_TERMS for sincheong/jijeong/deungrok/chulwon
REM    - src/synonym_resolver.py    : remove single-syllable mappings (sa/pal/ppae/beol)
REM    - src/korean_tokenizer.py    : add patent compound nouns to DOMAIN_TERMS
REM    - tests/test_patent_regression.py : 32 regression cases
REM ========================================================================
cd /d E:\GitHub\bonded-exhibition-chatbot-data
if errorlevel 1 (
    echo [ERROR] cd failed - check path
    pause
    exit /b 1
)

echo.
echo [1/6] Removing stale lock files
if exist .git\index.lock (
    echo   - removing .git\index.lock
    del /f /q .git\index.lock
)

echo.
echo [2/6] Current branch and status
git rev-parse --abbrev-ref HEAD
git status --short

echo.
echo [3/6] Running patent regression tests
python -m pytest tests/test_patent_regression.py -q
if errorlevel 1 (
    echo.
    echo [ERROR] regression tests failed - push aborted
    pause
    exit /b 1
)

echo.
echo [4/6] Staging patent fix files
git add src/spell_corrector.py src/synonym_resolver.py src/korean_tokenizer.py tests/test_patent_regression.py
if errorlevel 1 (
    echo [ERROR] git add failed
    pause
    exit /b 1
)
git status --short

echo.
echo [5/6] Creating commit
git commit -m "fix: improve patent question answer quality (retrieval/tokenizer/spell)" -m "BUG A: spell_corrector wrongly converts sincheong/jijeong to singo/gyujeong - add KNOWN_TERMS sincheong, jijeong, deungrok, chulwon" -m "BUG B: synonym_resolver single-syllable mappings (sa/pal/ppae/beol) caused wrong substring matches - remove 4 mappings" -m "BUG C: korean_tokenizer DOMAIN_TERMS missing patent compound nouns - add teukheo, teukheogigan, teukheosincheong, teukheojangso, teukheochuiso, teukheoyeonjang, teukheosincheongseo, seolchiteukheo, unyeongin" -m "tests: tests/test_patent_regression.py 32 cases (12 golden routing + 20 unit tests)"
if errorlevel 1 (
    echo.
    echo [ERROR] commit failed - push aborted
    pause
    exit /b 1
)

echo.
echo [6/6] Pushing to origin/main (no force)
git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] push failed - check network and credentials
    pause
    exit /b 1
)

echo.
echo [OK] Push complete to origin/main
git log --oneline -3
echo.
pause
