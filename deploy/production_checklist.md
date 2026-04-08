# 보세전시장 챗봇 배포 체크리스트

## 사전 준비

- [ ] `.env.example` → `.env` 복사 및 값 설정
- [ ] `CHATBOT_API_KEYS` 설정 (프로덕션에서 필수)
- [ ] `CHATBOT_CORS_ORIGINS` 허용 도메인 제한
- [ ] PostgreSQL 연결 정보 설정 (선택)

## Docker 빌드 및 실행

```bash
# 빌드
docker-compose build

# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f chatbot

# 헬스체크
curl http://localhost:8080/health
```

## 테스트 검증 (배포 전)

```bash
# 전체 코어 테스트
pytest tests/test_chatbot.py tests/test_classifier.py tests/test_policy_engine.py tests/test_entity_extractor.py tests/test_enhanced_pipeline.py -v

# 186개 테스트 전부 PASS 확인
```

## 배포 후 확인

- [ ] `/health` 엔드포인트 응답 200
- [ ] `/api/v1/chat` POST 요청 정상 응답
- [ ] FAQ 검색 동작 확인 ("보세구역이 뭐야?")
- [ ] Intent 분류 동작 확인
- [ ] Entity 추출 동작 확인
- [ ] PolicyEngine 위험도 평가 동작 확인
- [ ] 관리자 대시보드 접근 (`/admin`)

## 롤백

```bash
# 이전 버전으로 롤백
bash deploy/rollback.sh
```
