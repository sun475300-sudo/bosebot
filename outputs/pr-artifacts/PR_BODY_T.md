## What
Pure-Python language detection (Unicode block 휴리스틱, 외부 lib 의존 없음).

## File
`src/lang_detect.py`
- `detect(text) -> ko|en|zh|ja|ar|ru|mixed|unknown`
- Hiragana/Katakana 우선 → ja
- `NON_KOREAN_NOTICE` 5개 언어 안내 메시지

## Tests
`tests/test_lang_detect.py` — 9 cases (각 언어 + 한국어+영어 혼합 + 빈 입력)
