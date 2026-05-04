@echo off
REM =====================================================================
REM  PUSH_CLASSIFIER_FIX_TO_MAIN.bat
REM
REM  분류기/카테고리 매핑 버그 3개 (live_chatbot_test_20260504 회귀) 수정
REM  - patent_duration  : "특허 기간" 질문이 EXHIBITION 으로 오분류되던 문제
REM  - goods_inspection : "물품 검사" 질문이 FOOD_TASTING 으로 오분류되던 문제
REM  - patent_infringement : "특허 침해품" 질문이 unknown 으로 폴백되던 문제
REM
REM  부수적으로 spell_corrector 의 오교정도 함께 수정:
REM  "물품 검사" -> "식품 검역" 으로 잘못 자동교정되던 문제
REM
REM  사용:  현재 파일 위치(repo root)에서 더블클릭 또는
REM         cmd> PUSH_CLASSIFIER_FIX_TO_MAIN.bat
REM
REM  주의:  force push 를 절대 사용하지 않습니다.
REM         회귀 테스트가 통과한 상태에서만 실행하십시오.
REM =====================================================================

setlocal
cd /d "%~dp0"

echo.
echo [1/5] 회귀 테스트 실행 중...
echo.
set SKIP_HEAVY_DEPS=1
python -m pytest ^
    tests/test_classifier.py ^
    tests/test_patent_qa_golden.py ^
    tests/test_bonded_notice_qa.py ^
    tests/test_intent_classification.py ^
    tests/test_smart_classifier.py ^
    tests/test_patent_regression.py
if errorlevel 1 (
    echo.
    echo [ERROR] 회귀 테스트 실패. 푸시 중단.
    pause
    exit /b 1
)

echo.
echo [2/5] 변경 파일 스테이징...
echo.
git add ^
    config/chatbot_config.json ^
    data/faq.json ^
    src/classifier.py ^
    src/chatbot.py ^
    src/spell_corrector.py ^
    tests/test_classifier.py ^
    tests/test_patent_regression.py ^
    tests/test_intent_classification.py ^
    scripts/live_chatbot_test.py ^
    reports/live_chatbot_test_20260504_100630.md ^
    PUSH_CLASSIFIER_FIX_TO_MAIN.bat
if errorlevel 1 (
    echo.
    echo [ERROR] git add 실패.
    pause
    exit /b 1
)

echo.
echo [3/5] 변경 사항 확인...
echo.
git status -s
echo.

echo [4/5] 커밋 작성...
git commit -m "fix(bonded): intent/category misclassification for patent_duration, goods_inspection, patent_infringement" -m "live_chatbot_test_20260504 에서 발견된 분류기 버그 3개 수정." -m "" -m "- PATENT, INSPECTION, PATENT_INFRINGEMENT 카테고리 신설" -m "- FOOD_TASTING 매칭 가드 추가 (시식/식품 컨텍스트 필수)" -m "- patent_duration / goods_inspection / patent_infringement fast-path intent" -m "- spell_corrector 에 '물품', '검사', '침해품' 등 핵심 토큰 등록 (오교정 방지)" -m "- 신규 FAQ 항목 (특허 기간 10년+갱신 / 물품 검사 / 특허 침해품)" -m "- 신규 회귀 테스트 13개 (tests/test_intent_classification.py)" -m "- 라이브 재테스트 리포트 첨부 (reports/live_chatbot_test_20260504_100630.md)"
if errorlevel 1 (
    echo.
    echo [INFO] 커밋할 변경사항이 없거나 실패. 계속 진행합니다.
)

echo.
echo [5/5] origin/main 푸시 (force 금지)...
echo.
git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] git push 실패. 원격 변경사항이 있을 수 있습니다.
    echo 먼저 git pull --rebase origin main 으로 원격 변경사항을 가져온 뒤 다시 시도하세요.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo  푸시 성공.
echo =====================================================================
echo.
pause
endlocal
