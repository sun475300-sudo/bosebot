---
name: gov-chatbot-architect
description: |
  한국 공공기관/정부 민원응대 챗봇의 아키텍처를 설계하고 구현하는 전문 스킬.
  기존 챗봇 프로젝트에 인텐트 분류(30+), 엔티티 추출(10+ 유형), FAQ 대규모 확장(300+),
  RAG 문서 시드, OpenAPI 스펙, PostgreSQL DDL, 정책 엔진(위험도 기반 답변 제어)을
  자동으로 설계·생성·통합한다. 보세전시장, 세관, 민원24, 정부24 등 공공 챗봇이나
  법령 기반 FAQ 시스템을 구축할 때 사용. "챗봇 설계", "FAQ 확장", "인텐트 설계",
  "정책 엔진", "정부 챗봇", "민원 챗봇", "공공 챗봇 아키텍처" 등의 키워드로 트리거.
---

# 공공기관 챗봇 아키텍처 설계 스킬

## 개요

이 스킬은 한국 공공기관/정부 민원응대 챗봇을 **프로덕션 수준**으로 설계·구현하는 워크플로우를 제공한다.
기존 간단한 FAQ 챗봇을 정부 서비스 품질의 시스템으로 업그레이드하는 데 최적화되어 있다.

## 워크플로우

### Phase 1: 현황 분석
기존 프로젝트 구조를 먼저 파악한다:
- `src/` 디렉토리의 기존 모듈 구조 (chatbot.py, classifier.py 등)
- `data/faq.json`의 현재 FAQ 항목 수와 형식
- 기존 검색 파이프라인 (키워드 → TF-IDF → BM25 → 벡터 → LLM)
- 테스트 커버리지 (`tests/`)

### Phase 2: 데이터 설계 (병렬 실행 권장)
아래 파일들을 **동시에** 생성한다. 각각 독립적이므로 에이전트를 병렬로 활용하면 빠르다.

#### 2-1. 인텐트 정의 (`data/intents.json`)
- 도메인별 6그룹, 총 30개 인텐트
- 각 인텐트: id, domain, name_ko, name_en, description, example_queries(5+), required_entities, optional_entities, follow_up_intents, escalation_trigger, risk_level
- risk_level 분포: low 30%, medium 50%, high 15%, critical 5%

#### 2-2. 엔티티 정의 (`data/entities.json`)
- 10개 엔티티 유형 (user_type, event_type, item_type, action_type, location, date_range, declaration_status, area_type, document_type, risk_flag)
- 각 유형: values 배열 (value, synonyms, description), extraction_patterns (정규식)

#### 2-3. FAQ 대규모 확장 (`data/faq.json`)
- 기존 50개 → 300개로 확장
- 신규 포맷: id, intent_id, category, canonical_question, user_variants(3-5), answer_short, answer_long, citations, entities, risk_level, escalation_rule, owner_dept, keywords
- 10개 카테고리 × 30개 = 300개
- **중요**: 기존 코드와의 호환성을 위해 `question`/`answer`/`legal_basis` 키도 함께 유지하거나, chatbot.py에 정규화 레이어 추가

#### 2-4. RAG 문서 시드 (`data/rag_documents.jsonl`)
- 50개 시드 문서 (JSONL 형식)
- source_type: 법령, 고시, 훈령, 해석례, FAQ, 가이드
- 실제 법적 근거 포함 (관세법, 시행령, 고시 등)

### Phase 3: API/DB 설계 (병렬 실행 권장)

#### 3-1. OpenAPI 스펙 (`api/openapi.yaml`)
- Chat API (3 endpoints): 대화, 이력, 피드백
- Admin API (8 endpoints): FAQ/인텐트/엔티티 CRUD, 에스컬레이션
- RAG API (3 endpoints): 문서 업로드/검색/수정
- Dashboard API (3 endpoints): 메트릭, 만족도, 인텐트 분석
- JWT 인증, 에러 스키마, 페이지네이션

#### 3-2. PostgreSQL DDL (`db/schema.sql`)
- 23개 테이블: Core(6) + FAQ(4) + RAG(3) + Policy(3) + Analytics(3) + System(4)
- GIN 인덱스 (JSONB, tsvector)
- 트리거 (updated_at, 감사 로깅)
- RBAC (admin, operator, readonly)

### Phase 4: 코드 구현 (순차 실행)

#### 4-1. 정책 엔진 (`src/policy_engine.py`)
```
RiskLevel(Enum): LOW, MEDIUM, HIGH, CRITICAL
PolicyRule: rule_id, name, condition, action, risk_level, message_template, escalation_target
PolicyDecision: risk_level, disclaimers, requires_escalation, escalation_target, filtered_answer
PolicyEngine:
  - evaluate(query, intent, entities, faq_item) → PolicyDecision
  - get_disclaimer(risk_level) → str (한국어 면책문구)
  - apply_answer_filter(answer, risk_level) → str
  - should_escalate(decision) → bool
  - log_policy_decision(decision) → audit JSONL
```

내장 규칙 10개:
| 트리거 | 위험도 | 액션 |
|--------|--------|------|
| 세금/관세 계산 | HIGH | 면책조항 필수 |
| 벌칙/처벌 질문 | HIGH | 전문가 상담 권유 |
| 개인정보 포함 | CRITICAL | 즉시 에스컬레이션 |
| 전략물자 관련 | CRITICAL | 즉시 에스컬레이션 |
| 법적 해석 요청 | MEDIUM | 면책 추가 |
| 식품안전 관련 | MEDIUM | 식약처 확인 권유 |

#### 4-2. 엔티티 추출기 (`src/entity_extractor.py`)
- `data/entities.json` 로드
- 패턴 매칭 + 동의어 매칭
- 신뢰도 점수 반환
- 데이터 파일 없으면 graceful 비활성화

#### 4-3. 분류기 업데이트 (`src/classifier.py`)
- `IntentClassifier` 클래스 추가 (data/intents.json 로드)
- `classify_intent(query) → (intent_id, confidence)` 추가
- 기존 `classify_query()` 함수는 유지 (하위 호환)
- 인텐트 → 기존 10-category 매핑

#### 4-4. 챗봇 통합 (`src/chatbot.py`)
- FAQ 정규화 레이어 추가 (canonical_question↔question, answer_long↔answer, citations↔legal_basis)
- 새 파이프라인: 전처리 → 인텐트 분류 → 엔티티 추출 → 카테고리 매핑 → FAQ 매칭 → 정책 평가 → 답변 필터링 → 에스컬레이션 → 응답
- `process_query(query, include_metadata=True)` 반환: response, intent_id, intent_confidence, category, entities, risk_level, policy_decision, escalation_triggered
- 기존 동작 완전 유지 (include_metadata=False가 기본값)

### Phase 5: 검증
- 기존 테스트 실행하여 하위 호환성 확인
- FAQ ID 변경으로 인한 테스트 실패 → 카테고리 기반 assertion으로 수정
- 새 데이터 파일 JSON 유효성 검증

## 한국어 면책문구 표준

| 위험도 | 면책문구 |
|--------|----------|
| LOW | (없음) |
| MEDIUM | 본 안내는 일반적인 참고 정보이며, 구체적인 사실관계에 따라 달라질 수 있습니다. |
| HIGH | 본 답변은 법적 효력이 없으며, 정확한 사항은 관할 세관에 문의하시기 바랍니다. |
| CRITICAL | 이 질문은 전문 상담이 필요합니다. 관할 세관 보세산업과(☎ 125)로 문의해 주시기 바랍니다. |

## 핵심 원칙

1. **하위 호환**: 기존 코드/테스트가 깨지면 안 된다. 새 기능은 opt-in 방식으로 추가
2. **Graceful 비활성화**: 데이터 파일이 없으면 새 기능만 비활성화되고 기존 동작 유지
3. **병렬 생성**: 데이터 파일들은 독립적이므로 에이전트 병렬 실행으로 속도 향상
4. **실제 법적 근거**: placeholder가 아닌 실제 관세법/시행령/고시 조문 인용
5. **감사 추적**: 모든 정책 결정을 JSONL로 로깅 (정부 시스템 감사 요건)
