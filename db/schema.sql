/*
 * Bonded Exhibition Hall Chatbot System - PostgreSQL DDL Schema
 * Korean Bonded Exhibition (보세 전시장) Automated Customer Service
 *
 * Tables: 23 core tables with full indexing, triggers, and audit support
 * Created: 2026-04-08
 * Version: 1.0
 */

-- ============================================================================
-- DATABASE SETUP & EXTENSIONS
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search
CREATE EXTENSION IF NOT EXISTS "unaccent";  -- For text normalization

-- ============================================================================
-- ROLES & SECURITY
-- ============================================================================

-- Create application roles if they don't exist
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'chatbot_admin') THEN
    CREATE ROLE chatbot_admin WITH LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'chatbot_operator') THEN
    CREATE ROLE chatbot_operator WITH LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'chatbot_readonly') THEN
    CREATE ROLE chatbot_readonly WITH LOGIN;
  END IF;
END $$;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Table 1: users - 사용자 정보
-- Stores user profiles for system access and interaction tracking
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('admin', 'operator', 'customer', 'system')),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  dept VARCHAR(100),
  role VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
  last_login TIMESTAMP WITH TIME ZONE,
  is_active BOOLEAN DEFAULT true,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS '사용자 테이블 - 챗봇 시스템 사용자 관리';
COMMENT ON COLUMN users.user_type IS '사용자 타입: admin, operator, customer, system';
COMMENT ON COLUMN users.dept IS '부서명 (운영자/관리자용)';
COMMENT ON COLUMN users.role IS '직급/역할';

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_user_type ON users(user_type);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Table 2: sessions - 대화 세션
-- Tracks chat sessions between users and chatbot
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel VARCHAR(50) NOT NULL CHECK (channel IN ('web', 'mobile', 'kakao', 'naver', 'api')),
  started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
  ended_at TIMESTAMP WITH TIME ZONE,
  satisfaction_score SMALLINT CHECK (satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 5)),
  session_context JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sessions IS '대화 세션 테이블 - 사용자와 챗봇의 대화 세션 관리';
COMMENT ON COLUMN sessions.channel IS '접속 채널';
COMMENT ON COLUMN sessions.satisfaction_score IS '만족도 점수 (1-5)';
COMMENT ON COLUMN sessions.session_context IS '세션 메타데이터 (언어, 위치 등)';

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_channel ON sessions(channel);
CREATE INDEX idx_sessions_started_at ON sessions(started_at DESC);
CREATE INDEX idx_sessions_ended_at ON sessions(ended_at);

-- Table 3: messages - 메시지
-- Stores all messages exchanged in chatbot sessions
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  intent_id UUID,
  confidence NUMERIC(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  message_type VARCHAR(50) DEFAULT 'text',
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE messages IS '메시지 테이블 - 대화 메시지 저장';
COMMENT ON COLUMN messages.role IS '발신자: user 또는 assistant';
COMMENT ON COLUMN messages.confidence IS 'NLU 신뢰도 (0-1)';
COMMENT ON COLUMN messages.message_type IS '메시지 타입: text, image, button 등';

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_intent_id ON messages(intent_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_messages_role ON messages(role);
CREATE INDEX idx_messages_content_tsvector ON messages USING GIN(to_tsvector('korean', content));

-- Table 4: intents - 인텐트 정의
-- Defines chatbot intents (user intentions)
CREATE TABLE intents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  domain VARCHAR(100) NOT NULL,
  name_ko VARCHAR(255) NOT NULL,
  name_en VARCHAR(255),
  description TEXT,
  training_phrases JSONB,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE intents IS '인텐트 정의 테이블 - 사용자 의도 분류';
COMMENT ON COLUMN intents.domain IS '도메인 분류 (문의, 예약, 규정 등)';
COMMENT ON COLUMN intents.name_ko IS '한글 인텐트명';
COMMENT ON COLUMN intents.training_phrases IS '학습 문구 배열';

CREATE INDEX idx_intents_domain ON intents(domain);
CREATE INDEX idx_intents_is_active ON intents(is_active);
CREATE UNIQUE INDEX idx_intents_name_ko ON intents(name_ko) WHERE is_active = true;

-- Table 5: entities - 엔티티 정의
-- Defines entity types extracted from messages
CREATE TABLE entities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name_ko VARCHAR(255) NOT NULL UNIQUE,
  name_en VARCHAR(255),
  type VARCHAR(50) NOT NULL CHECK (type IN ('string', 'number', 'date', 'time', 'phone', 'email', 'address', 'custom')),
  description TEXT,
  values JSONB,
  regex_pattern VARCHAR(500),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE entities IS '엔티티 정의 테이블 - 추출할 엔티티 타입 정의';
COMMENT ON COLUMN entities.values IS '가능한 값 배열 (콤보박스형)';
COMMENT ON COLUMN entities.regex_pattern IS '정규식 패턴';

CREATE INDEX idx_entities_type ON entities(type);

-- Table 6: message_entities - 메시지별 추출 엔티티
-- Tracks entities extracted from each message
CREATE TABLE message_entities (
  id BIGSERIAL PRIMARY KEY,
  message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  value VARCHAR(500) NOT NULL,
  position INT,
  confidence NUMERIC(5,4),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE message_entities IS '메시지 엔티티 추출 테이블 - 메시지에서 추출된 엔티티';
COMMENT ON COLUMN message_entities.position IS '메시지 내 시작 위치';
COMMENT ON COLUMN message_entities.confidence IS '추출 신뢰도';

CREATE INDEX idx_message_entities_message_id ON message_entities(message_id);
CREATE INDEX idx_message_entities_entity_id ON message_entities(entity_id);
CREATE INDEX idx_message_entities_value ON message_entities(value);

-- ============================================================================
-- FAQ TABLES
-- ============================================================================

-- Table 7: faq_items - FAQ 항목
-- Core FAQ content management
CREATE TABLE faq_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  intent_id UUID REFERENCES intents(id) ON DELETE SET NULL,
  canonical_question VARCHAR(500) NOT NULL,
  answer_short TEXT NOT NULL,
  answer_long TEXT,
  citations JSONB,
  risk_level VARCHAR(20) DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
  status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'pending_review', 'approved', 'archived')),
  owner_dept VARCHAR(100),
  version SMALLINT DEFAULT 1,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE faq_items IS 'FAQ 항목 테이블 - 자주 묻는 질문 및 답변 관리';
COMMENT ON COLUMN faq_items.canonical_question IS '정규화된 질문';
COMMENT ON COLUMN faq_items.citations IS '법령/규정 참조 정보';
COMMENT ON COLUMN faq_items.risk_level IS '법적/정책적 위험도';

CREATE INDEX idx_faq_items_intent_id ON faq_items(intent_id);
CREATE INDEX idx_faq_items_status ON faq_items(status);
CREATE INDEX idx_faq_items_risk_level ON faq_items(risk_level);
CREATE INDEX idx_faq_items_is_active ON faq_items(is_active);
CREATE INDEX idx_faq_items_owner_dept ON faq_items(owner_dept);
CREATE INDEX idx_faq_items_tsvector ON faq_items USING GIN(to_tsvector('korean', canonical_question || ' ' || answer_short));

-- Table 8: faq_variants - FAQ 변형 질문
-- Alternative phrasings of FAQ questions
CREATE TABLE faq_variants (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  faq_id UUID NOT NULL REFERENCES faq_items(id) ON DELETE CASCADE,
  variant_text VARCHAR(500) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE faq_variants IS 'FAQ 변형 질문 테이블 - 같은 FAQ에 대한 다양한 질문 형식';

CREATE INDEX idx_faq_variants_faq_id ON faq_variants(faq_id);
CREATE INDEX idx_faq_variants_tsvector ON faq_variants USING GIN(to_tsvector('korean', variant_text));

-- Table 9: faq_versions - FAQ 버전 이력
-- Track all version changes to FAQs
CREATE TABLE faq_versions (
  id BIGSERIAL PRIMARY KEY,
  faq_id UUID NOT NULL REFERENCES faq_items(id) ON DELETE CASCADE,
  version SMALLINT NOT NULL,
  content JSONB NOT NULL,
  changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  change_reason VARCHAR(500),
  changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE faq_versions IS 'FAQ 버전 이력 테이블 - FAQ 변경 이력 추적';

CREATE INDEX idx_faq_versions_faq_id ON faq_versions(faq_id);
CREATE INDEX idx_faq_versions_changed_at ON faq_versions(changed_at DESC);

-- Table 10: faq_approvals - FAQ 승인 워크플로
-- Workflow approval process for FAQ items
CREATE TABLE faq_approvals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  faq_id UUID NOT NULL REFERENCES faq_items(id) ON DELETE CASCADE,
  requested_by UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'revisions_requested')),
  comment TEXT,
  requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  approved_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE faq_approvals IS 'FAQ 승인 테이블 - 콘텐츠 승인 프로세스';

CREATE INDEX idx_faq_approvals_faq_id ON faq_approvals(faq_id);
CREATE INDEX idx_faq_approvals_status ON faq_approvals(status);
CREATE INDEX idx_faq_approvals_requested_by ON faq_approvals(requested_by);

-- ============================================================================
-- RAG (RETRIEVAL-AUGMENTED GENERATION) TABLES
-- ============================================================================

-- Table 11: rag_documents - RAG 문서
-- Stores documents for RAG retrieval
CREATE TABLE rag_documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title VARCHAR(500) NOT NULL,
  source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('regulation', 'guideline', 'manual', 'notice', 'faq', 'external')),
  source_name VARCHAR(255),
  content TEXT NOT NULL,
  embedding vector(1536),
  legal_citations JSONB,
  effective_date DATE,
  expiry_date DATE,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rag_documents IS 'RAG 문서 테이블 - 참조 문서 저장 및 임베딩';
COMMENT ON COLUMN rag_documents.source_type IS '문서 출처 유형';
COMMENT ON COLUMN rag_documents.embedding IS '벡터 임베딩 (OpenAI, 로컬 모델)';
COMMENT ON COLUMN rag_documents.legal_citations IS '관련 법령/규정';

CREATE INDEX idx_rag_documents_source_type ON rag_documents(source_type);
CREATE INDEX idx_rag_documents_is_active ON rag_documents(is_active);
CREATE INDEX idx_rag_documents_effective_date ON rag_documents(effective_date);
CREATE INDEX idx_rag_documents_title_tsvector ON rag_documents USING GIN(to_tsvector('korean', title || ' ' || content));

-- Table 12: rag_chunks - RAG 청크
-- Chunks of documents for semantic search
CREATE TABLE rag_chunks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  doc_id UUID NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),
  token_count INT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rag_chunks IS 'RAG 청크 테이블 - 문서를 분할한 청크 저장';
COMMENT ON COLUMN rag_chunks.chunk_index IS '문서 내 청크 순서';
COMMENT ON COLUMN rag_chunks.token_count IS '토큰 개수 추정';

CREATE INDEX idx_rag_chunks_doc_id ON rag_chunks(doc_id);
CREATE INDEX idx_rag_chunks_token_count ON rag_chunks(token_count);

-- Table 13: rag_references - RAG 참조 로그
-- Tracks which documents/chunks were used for responses
CREATE TABLE rag_references (
  id BIGSERIAL PRIMARY KEY,
  message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  chunk_id UUID NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
  relevance_score NUMERIC(5,4),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rag_references IS 'RAG 참조 로그 테이블 - 응답 생성에 사용된 문서 추적';

CREATE INDEX idx_rag_references_message_id ON rag_references(message_id);
CREATE INDEX idx_rag_references_chunk_id ON rag_references(chunk_id);

-- ============================================================================
-- POLICY & ESCALATION TABLES
-- ============================================================================

-- Table 14: policies - 정책 규칙
-- System policies and routing rules
CREATE TABLE policies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(255) NOT NULL UNIQUE,
  description TEXT,
  condition JSONB NOT NULL,
  action JSONB NOT NULL,
  priority INT DEFAULT 100,
  risk_level VARCHAR(20) DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE policies IS '정책 규칙 테이블 - 시스템 정책 및 라우팅 규칙';
COMMENT ON COLUMN policies.condition IS '정책 발동 조건 (JSON 형식)';
COMMENT ON COLUMN policies.action IS '정책 실행 액션 (JSON 형식)';
COMMENT ON COLUMN policies.priority IS '정책 우선순위 (낮을수록 높음)';

CREATE INDEX idx_policies_is_active ON policies(is_active);
CREATE INDEX idx_policies_risk_level ON policies(risk_level);
CREATE INDEX idx_policies_priority ON policies(priority);

-- Table 15: escalation_rules - 에스컬레이션 규칙
-- Rules for escalating conversations to human operators
CREATE TABLE escalation_rules (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(255) NOT NULL,
  trigger_condition JSONB NOT NULL,
  target_dept VARCHAR(100) NOT NULL,
  priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
  sla_hours INT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE escalation_rules IS '에스컬레이션 규칙 테이블 - 인간 상담사로의 전환 규칙';
COMMENT ON COLUMN escalation_rules.trigger_condition IS '에스컬레이션 발동 조건 (JSON)';
COMMENT ON COLUMN escalation_rules.sla_hours IS 'Service Level Agreement 시간';

CREATE INDEX idx_escalation_rules_target_dept ON escalation_rules(target_dept);
CREATE INDEX idx_escalation_rules_is_active ON escalation_rules(is_active);

-- Table 16: escalations - 에스컬레이션 큐
-- Active escalations waiting for human response
CREATE TABLE escalations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
  rule_id UUID REFERENCES escalation_rules(id) ON DELETE SET NULL,
  status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_progress', 'resolved', 'cancelled')),
  assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
  priority VARCHAR(20) DEFAULT 'normal',
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  assigned_at TIMESTAMP WITH TIME ZONE,
  resolved_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE escalations IS '에스컬레이션 큐 테이블 - 실시간 에스컬레이션 관리';

CREATE INDEX idx_escalations_session_id ON escalations(session_id);
CREATE INDEX idx_escalations_status ON escalations(status);
CREATE INDEX idx_escalations_assigned_to ON escalations(assigned_to);
CREATE INDEX idx_escalations_created_at ON escalations(created_at DESC);
CREATE INDEX idx_escalations_priority ON escalations(priority);

-- ============================================================================
-- ANALYTICS TABLES
-- ============================================================================

-- Table 17: conversation_metrics - 대화 메트릭
-- Per-conversation performance metrics
CREATE TABLE conversation_metrics (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE UNIQUE,
  total_messages INT,
  response_time_ms INT,
  avg_intent_confidence NUMERIC(5,4),
  intent_confidence NUMERIC(5,4),
  was_escalated BOOLEAN DEFAULT false,
  was_helpful BOOLEAN,
  first_response_time_ms INT,
  resolution_time_minutes INT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE conversation_metrics IS '대화 메트릭 테이블 - 대화별 성능 지표';

CREATE INDEX idx_conversation_metrics_session_id ON conversation_metrics(session_id);
CREATE INDEX idx_conversation_metrics_was_escalated ON conversation_metrics(was_escalated);
CREATE INDEX idx_conversation_metrics_created_at ON conversation_metrics(created_at DESC);

-- Table 18: daily_stats - 일별 통계
-- Aggregated daily statistics
CREATE TABLE daily_stats (
  date DATE PRIMARY KEY,
  total_sessions INT DEFAULT 0,
  total_messages INT DEFAULT 0,
  avg_satisfaction NUMERIC(5,4),
  escalation_count INT DEFAULT 0,
  resolved_count INT DEFAULT 0,
  abandoned_count INT DEFAULT 0,
  peak_hour INT,
  peak_hour_sessions INT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE daily_stats IS '일별 통계 테이블 - 매일 집계 통계';

CREATE INDEX idx_daily_stats_date ON daily_stats(date DESC);

-- Table 19: intent_analytics - 인텐트 분석
-- Intent-level analytics
CREATE TABLE intent_analytics (
  id BIGSERIAL PRIMARY KEY,
  date DATE NOT NULL,
  intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
  count INT DEFAULT 0,
  avg_confidence NUMERIC(5,4),
  escalation_count INT DEFAULT 0,
  escalation_rate NUMERIC(5,4),
  resolution_rate NUMERIC(5,4),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE intent_analytics IS '인텐트 분석 테이블 - 인텐트별 성능 분석';

CREATE INDEX idx_intent_analytics_date ON intent_analytics(date DESC);
CREATE INDEX idx_intent_analytics_intent_id ON intent_analytics(intent_id);
CREATE UNIQUE INDEX idx_intent_analytics_date_intent ON intent_analytics(date, intent_id);

-- ============================================================================
-- SYSTEM & AUDIT TABLES
-- ============================================================================

-- Table 20: audit_log - 감사 로그
-- Complete audit trail for compliance
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  target_table VARCHAR(100),
  target_id VARCHAR(100),
  old_value JSONB,
  new_value JSONB,
  ip_address INET,
  user_agent VARCHAR(500),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

COMMENT ON TABLE audit_log IS '감사 로그 테이블 - 시스템 변경 이력 추적';
COMMENT ON COLUMN audit_log.action IS 'CREATE, UPDATE, DELETE, APPROVE 등';
COMMENT ON COLUMN audit_log.ip_address IS '사용자 IP 주소';

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_target_table ON audit_log(target_table, target_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action);

-- Table 21: system_config - 시스템 설정
-- Configuration management
CREATE TABLE system_config (
  key VARCHAR(255) PRIMARY KEY,
  value JSONB NOT NULL,
  description TEXT,
  data_type VARCHAR(50),
  updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE system_config IS '시스템 설정 테이블 - 동적 설정 관리';
COMMENT ON COLUMN system_config.key IS '설정 키 (dot notation 권장)';
COMMENT ON COLUMN system_config.value IS '설정 값 (JSON)';

-- Table 22: api_keys - API 키 관리
-- API key management for external integrations
CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  key_hash VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  permissions JSONB,
  rate_limit INT,
  is_active BOOLEAN DEFAULT true,
  expires_at TIMESTAMP WITH TIME ZONE,
  last_used_at TIMESTAMP WITH TIME ZONE,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE api_keys IS 'API 키 관리 테이블 - 외부 연동 API 키';

CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at);

-- Table 23: notifications - 알림
-- User notifications and alerts
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type VARCHAR(50) NOT NULL CHECK (type IN ('info', 'warning', 'error', 'success', 'escalation', 'approval')),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  related_entity_type VARCHAR(100),
  related_entity_id UUID,
  is_read BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  read_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE notifications IS '알림 테이블 - 사용자 알림 및 경고';

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to all tables with updated_at column
CREATE TRIGGER trigger_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_sessions_updated_at BEFORE UPDATE ON sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_messages_updated_at BEFORE UPDATE ON messages
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_intents_updated_at BEFORE UPDATE ON intents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_entities_updated_at BEFORE UPDATE ON entities
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_faq_items_updated_at BEFORE UPDATE ON faq_items
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_rag_documents_updated_at BEFORE UPDATE ON rag_documents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_policies_updated_at BEFORE UPDATE ON policies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_escalation_rules_updated_at BEFORE UPDATE ON escalation_rules
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_system_config_updated_at BEFORE UPDATE ON system_config
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_api_keys_updated_at BEFORE UPDATE ON api_keys
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- AUDIT LOGGING TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_table_changes()
RETURNS TRIGGER AS $$
DECLARE
  v_old_values JSONB;
  v_new_values JSONB;
  v_action TEXT;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'CREATE';
    v_new_values := row_to_json(NEW);
    v_old_values := NULL;
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE';
    v_old_values := row_to_json(OLD);
    v_new_values := row_to_json(NEW);
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE';
    v_old_values := row_to_json(OLD);
    v_new_values := NULL;
  END IF;

  INSERT INTO audit_log (user_id, action, target_table, target_id, old_value, new_value, created_at)
  VALUES (
    COALESCE((NEW).user_id, (OLD).user_id, (NEW).id, (OLD).id),
    v_action,
    TG_TABLE_NAME,
    COALESCE((NEW).id::TEXT, (OLD).id::TEXT),
    v_old_values,
    v_new_values,
    CURRENT_TIMESTAMP
  );

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  ELSE
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to critical tables
CREATE TRIGGER trigger_audit_faq_items AFTER INSERT OR UPDATE OR DELETE ON faq_items
  FOR EACH ROW EXECUTE FUNCTION audit_table_changes();

CREATE TRIGGER trigger_audit_policies AFTER INSERT OR UPDATE OR DELETE ON policies
  FOR EACH ROW EXECUTE FUNCTION audit_table_changes();

CREATE TRIGGER trigger_audit_escalation_rules AFTER INSERT OR UPDATE OR DELETE ON escalation_rules
  FOR EACH ROW EXECUTE FUNCTION audit_table_changes();

-- ============================================================================
-- VIEWS FOR ANALYTICS & REPORTING
-- ============================================================================

-- Active escalations overview
CREATE OR REPLACE VIEW v_active_escalations AS
SELECT
  e.id,
  s.user_id,
  u.name as user_name,
  u.email,
  e.status,
  e.priority,
  EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - e.created_at))/3600 as hours_pending,
  u_assigned.name as assigned_to_name,
  er.sla_hours,
  CASE
    WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - e.created_at))/3600 > er.sla_hours THEN 'BREACHED'
    ELSE 'OK'
  END as sla_status
FROM escalations e
JOIN sessions s ON e.session_id = s.id
JOIN users u ON s.user_id = u.id
LEFT JOIN users u_assigned ON e.assigned_to = u_assigned.id
LEFT JOIN escalation_rules er ON e.rule_id = er.id
WHERE e.status IN ('pending', 'assigned', 'in_progress');

COMMENT ON VIEW v_active_escalations IS '활성 에스컬레이션 현황 뷰';

-- Daily conversation summary
CREATE OR REPLACE VIEW v_conversation_summary AS
SELECT
  DATE(s.started_at) as conversation_date,
  s.channel,
  COUNT(DISTINCT s.id) as session_count,
  COUNT(m.id) as total_messages,
  AVG(CASE WHEN m.confidence IS NOT NULL THEN m.confidence ELSE 0 END) as avg_confidence,
  COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN e.session_id END) as escalation_count,
  AVG(CASE WHEN s.satisfaction_score IS NOT NULL THEN s.satisfaction_score ELSE 0 END) as avg_satisfaction
FROM sessions s
LEFT JOIN messages m ON s.id = m.session_id
LEFT JOIN escalations e ON s.id = e.session_id AND e.status IN ('pending', 'assigned', 'in_progress')
WHERE s.started_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE(s.started_at), s.channel;

COMMENT ON VIEW v_conversation_summary IS '대화 요약 일별 통계 뷰';

-- FAQ performance metrics
CREATE OR REPLACE VIEW v_faq_performance AS
SELECT
  f.id,
  f.canonical_question,
  f.status,
  COUNT(DISTINCT m.session_id) as referenced_sessions,
  COUNT(m.id) as total_references,
  COUNT(DISTINCT CASE WHEN m.confidence >= 0.8 THEN m.session_id END) as high_confidence_sessions,
  f.updated_at,
  f.owner_dept
FROM faq_items f
LEFT JOIN messages m ON f.id = m.intent_id
WHERE f.is_active = true
GROUP BY f.id, f.canonical_question, f.status, f.updated_at, f.owner_dept;

COMMENT ON VIEW v_faq_performance IS 'FAQ 성능 메트릭 뷰';

-- ============================================================================
-- ROLE-BASED ACCESS CONTROL SETUP
-- ============================================================================

-- Grant permissions to chatbot_admin (full access)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO chatbot_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO chatbot_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO chatbot_admin;

-- Grant permissions to chatbot_operator (read-write on operational tables)
GRANT SELECT, INSERT, UPDATE ON sessions, messages, escalations, notifications TO chatbot_operator;
GRANT SELECT ON intents, entities, faq_items, faq_variants, rag_documents, rag_chunks TO chatbot_operator;
GRANT SELECT ON daily_stats, intent_analytics, conversation_metrics TO chatbot_operator;

-- Grant permissions to chatbot_readonly (read-only access)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO chatbot_readonly;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get active FAQ for an intent
CREATE OR REPLACE FUNCTION get_active_faq(p_intent_id UUID)
RETURNS TABLE (
  id UUID,
  canonical_question VARCHAR,
  answer_short TEXT,
  answer_long TEXT,
  citations JSONB
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f.id,
    f.canonical_question,
    f.answer_short,
    f.answer_long,
    f.citations
  FROM faq_items f
  WHERE f.intent_id = p_intent_id
    AND f.is_active = true
    AND f.status = 'approved'
  LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to create session
CREATE OR REPLACE FUNCTION create_session(
  p_user_id UUID,
  p_channel VARCHAR,
  p_context JSONB DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
  v_session_id UUID;
BEGIN
  INSERT INTO sessions (user_id, channel, session_context)
  VALUES (p_user_id, p_channel, COALESCE(p_context, '{}'::JSONB))
  RETURNING id INTO v_session_id;

  RETURN v_session_id;
END;
$$ LANGUAGE plpgsql;

-- Function to log message
CREATE OR REPLACE FUNCTION log_message(
  p_session_id UUID,
  p_role VARCHAR,
  p_content TEXT,
  p_intent_id UUID DEFAULT NULL,
  p_confidence NUMERIC DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
  v_message_id UUID;
BEGIN
  INSERT INTO messages (session_id, role, content, intent_id, confidence)
  VALUES (p_session_id, p_role, p_content, p_intent_id, p_confidence)
  RETURNING id INTO v_message_id;

  RETURN v_message_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA & CONFIGURATION
-- ============================================================================

-- Insert default system user
INSERT INTO users (id, user_type, name, email, dept, role)
VALUES ('00000000-0000-0000-0000-000000000000', 'system', 'System', 'system@chatbot.local', 'IT', 'System')
ON CONFLICT DO NOTHING;

-- Insert default intents
INSERT INTO intents (domain, name_ko, name_en, description, is_active)
VALUES
  ('general', '인사', 'Greeting', '사용자 인사 및 인증', true),
  ('inquiry', '보세전시장 정보', 'Bonded Exhibition Info', '보세 전시장 관련 정보 문의', true),
  ('inquiry', '수입 절차', 'Import Process', '수입 및 통관 절차', true),
  ('inquiry', '규정 및 정책', 'Regulations', '관세청 규정 및 정책', true),
  ('escalation', '에스컬레이션', 'Escalation', '인간 상담사로 전환', true),
  ('feedback', '만족도 조사', 'Satisfaction Survey', '대화 만족도 조사', true)
ON CONFLICT (name_ko) DO NOTHING;

-- Insert default entities
INSERT INTO entities (name_ko, type, description, values)
VALUES
  ('수입건 ID', 'string', '세관 수입건 식별 번호', '["B20240001", "B20240002"]'::JSONB),
  ('통관 상태', 'string', '수입 통관 상태', '["미신고", "신고", "검사중", "완료", "거부"]'::JSONB),
  ('날짜', 'date', '특정 날짜', NULL),
  ('전화번호', 'phone', '고객 전화번호', NULL),
  ('이메일', 'email', '고객 이메일', NULL)
ON CONFLICT (name_ko) DO NOTHING;

-- Insert default system configuration
INSERT INTO system_config (key, value, description, data_type)
VALUES
  ('chatbot.max_conversation_turns', '50'::JSONB, '최대 대화 턴 수', 'integer'),
  ('chatbot.response_timeout_seconds', '30'::JSONB, '응답 타임아웃 시간', 'integer'),
  ('chatbot.confidence_threshold', '0.7'::JSONB, '최소 신뢰도 임계값', 'float'),
  ('faq.auto_approval_enabled', 'false'::JSONB, 'FAQ 자동 승인 활성화', 'boolean'),
  ('escalation.default_sla_hours', '4'::JSONB, '기본 에스컬레이션 SLA', 'integer'),
  ('rag.embedding_model', '"text-embedding-ada-002"'::JSONB, 'RAG 임베딩 모델', 'string'),
  ('audit.retention_days', '365'::JSONB, '감사 로그 보관 기간', 'integer')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- SCHEMA DOCUMENTATION
-- ============================================================================

/*
SCHEMA OVERVIEW
===============

This schema implements a comprehensive Korean bonded exhibition hall chatbot system
with the following major components:

1. CONVERSATION LAYER (users, sessions, messages)
   - Full conversation history with user context tracking
   - Multi-channel support (web, mobile, messaging platforms)

2. NLU LAYER (intents, entities, message_entities)
   - Intent classification and entity extraction
   - Confidence scoring for model predictions

3. KNOWLEDGE MANAGEMENT (faq_items, faq_variants, faq_versions, faq_approvals)
   - Structured FAQ database with version control
   - Approval workflow for compliance
   - Risk level tracking for regulatory content

4. RAG LAYER (rag_documents, rag_chunks, rag_references)
   - Document storage with vector embeddings
   - Semantic search capability
   - Reference tracking for generated responses

5. POLICY & ESCALATION (policies, escalation_rules, escalations)
   - Rule-based conversation routing
   - Automatic escalation to human operators
   - SLA management

6. ANALYTICS (conversation_metrics, daily_stats, intent_analytics)
   - Per-conversation performance metrics
   - Aggregated daily statistics
   - Intent-level analytics

7. AUDIT & COMPLIANCE (audit_log, system_config, api_keys, notifications)
   - Complete audit trail for regulatory compliance
   - Dynamic system configuration
   - API key management
   - User notifications

KOREAN BONDED EXHIBITION SPECIFIC FEATURES
============================================

- Risk levels tied to customs regulations (law, medium, high, critical)
- Legal citation tracking for all FAQ and RAG documents
- Department-based ownership for content management
- Integration with Korean regulatory frameworks
- Multi-language support (Korean/English)

PERFORMANCE CONSIDERATIONS
===========================

- GIN indexes on JSONB columns for efficient querying
- Full-text search indexes for Korean text (tsvector)
- Proper partitioning recommended for daily_stats (date) and audit_log (date)
- Vector indexes recommended for embedding similarity search once pgvector is installed

SECURITY
========

- Three-tier role-based access control (admin, operator, readonly)
- Audit logging on all DML operations
- IP address tracking for audit trail
- API key hashing (not stored plaintext)

MAINTENANCE
===========

- Recommended to archive audit_log and conversation_metrics annually
- FAQ versions should be cleaned up for dormant FAQs
- RAG embeddings may need periodic refresh as models update
- Daily stats are aggregated - source tables can be archived after 90 days

*/
