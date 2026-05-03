## What
FAQ 의도 분류 신뢰도 임계값 (`INTENT_CONFIDENCE_THRESHOLD`) 을 환경변수로 노출.

## File
- `src/chatbot.py` — 하드코드된 `0.3` 을 env 에서 읽고 [0.0, 1.0] 범위 검증

## Tests
`tests/test_confidence_threshold_env.py` — 4 cases (default / override / invalid / out-of-range)

## Risk
미설정 시 동작 동일 (default 0.3). 운영자가 deploy 별로 정확도 vs 회수율 trade-off 튜닝.
