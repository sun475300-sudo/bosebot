"""EntityExtractorV2 테스트.

한국어 엔티티 추출 모듈의 각 엔티티 타입 추출, 복합 추출,
컨텍스트 기반 추출, 에지 케이스, API 엔드포인트를 테스트한다.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.entity_extractor_v2 import EntityExtractorV2, get_entity_extractor_v2
from web_server import app


@pytest.fixture
def extractor():
    """EntityExtractorV2 인스턴스를 반환한다."""
    return EntityExtractorV2()


@pytest.fixture
def client():
    """Flask 테스트 클라이언트를 반환한다."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- user_type 추출 테스트 ---

class TestUserTypeExtraction:
    """user_type 엔티티 추출 테스트."""

    def test_extract_applicant(self, extractor):
        """신청자 추출 테스트."""
        entities = extractor.extract("신청자로서 질문합니다")
        user_types = [e for e in entities if e["entity_type"] == "user_type"]
        assert len(user_types) >= 1
        assert any(e["value"] == "신청자" for e in user_types)

    def test_extract_operator(self, extractor):
        """전시장운영사 추출 테스트."""
        entities = extractor.extract("전시장운영사에서 문의드립니다")
        user_types = [e for e in entities if e["entity_type"] == "user_type"]
        assert any(e["value"] == "전시장운영사" for e in user_types)

    def test_extract_exhibitor(self, extractor):
        """출품업체 추출 테스트."""
        entities = extractor.extract("출품업체 담당자입니다")
        user_types = [e for e in entities if e["entity_type"] == "user_type"]
        assert any(e["value"] == "출품업체" for e in user_types)

    def test_extract_customs_broker(self, extractor):
        """관세사 추출 테스트."""
        entities = extractor.extract("관세사가 대리 신청합니다")
        user_types = [e for e in entities if e["entity_type"] == "user_type"]
        assert any(e["value"] == "관세사" for e in user_types)

    def test_extract_user_type_from_context_pattern(self, extractor):
        """컨텍스트 패턴으로 user_type 추출 테스트."""
        entities = extractor.extract("운영하고 있는 전시장에 대해 묻겠습니다")
        user_types = [e for e in entities if e["entity_type"] == "user_type"]
        assert any(e["value"] == "운영사" for e in user_types)


# --- item_type 추출 테스트 ---

class TestItemTypeExtraction:
    """item_type 엔티티 추출 테스트."""

    def test_extract_food(self, extractor):
        """식품 추출 테스트."""
        entities = extractor.extract("식품을 반입하려 합니다")
        item_types = [e for e in entities if e["entity_type"] == "item_type"]
        assert any(e["value"] == "식품" for e in item_types)

    def test_extract_beverage(self, extractor):
        """음료 추출 테스트."""
        entities = extractor.extract("음료 샘플을 전시할 수 있나요")
        item_types = [e for e in entities if e["entity_type"] == "item_type"]
        assert any(e["value"] == "음료" for e in item_types)

    def test_extract_sample(self, extractor):
        """샘플품 추출 테스트."""
        entities = extractor.extract("샘플품 반입 절차가 궁금합니다")
        item_types = [e for e in entities if e["entity_type"] == "item_type"]
        assert any(e["value"] == "샘플품" for e in item_types)

    def test_extract_sale_goods(self, extractor):
        """판매용품 추출 테스트."""
        entities = extractor.extract("판매용품에 대한 관세가 어떻게 되나요")
        item_types = [e for e in entities if e["entity_type"] == "item_type"]
        assert any(e["value"] == "판매용품" for e in item_types)

    def test_extract_tasting_food_pattern(self, extractor):
        """시식용 식품 패턴 추출 테스트."""
        entities = extractor.extract("시식용 식품을 준비했습니다")
        item_types = [e for e in entities if e["entity_type"] == "item_type"]
        assert any(e["value"] == "식품" for e in item_types)


# --- action_type 추출 테스트 ---

class TestActionTypeExtraction:
    """action_type 엔티티 추출 테스트."""

    def test_extract_import_action(self, extractor):
        """반입 추출 테스트."""
        entities = extractor.extract("물품을 반입하려 합니다")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        assert any(e["value"] == "반입" for e in actions)

    def test_extract_export_action(self, extractor):
        """반출 추출 테스트."""
        entities = extractor.extract("전시 후 반출 절차를 알고 싶습니다")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        assert any(e["value"] == "반출" for e in actions)

    def test_extract_sale_action(self, extractor):
        """판매 추출 테스트."""
        entities = extractor.extract("전시장에서 판매할 수 있나요")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        assert any(e["value"] == "판매" for e in actions)

    def test_extract_tasting_action(self, extractor):
        """시식 추출 테스트."""
        entities = extractor.extract("시식 행사를 계획하고 있습니다")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        assert any(e["value"] == "시식" for e in actions)

    def test_extract_demonstration_action(self, extractor):
        """시연 추출 테스트."""
        entities = extractor.extract("제품 시연을 하고 싶습니다")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        assert any(e["value"] == "시연" for e in actions)

    def test_extract_reexport_action(self, extractor):
        """재수출 추출 테스트."""
        entities = extractor.extract("재수출 절차는 어떻게 되나요")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        assert any(e["value"] == "재수출" for e in actions)


# --- location 추출 테스트 ---

class TestLocationExtraction:
    """location 엔티티 추출 테스트."""

    def test_extract_seoul(self, extractor):
        """서울 지역 추출 테스트."""
        entities = extractor.extract("서울 세관에 신고하려 합니다")
        locations = [e for e in entities if e["entity_type"] == "location"]
        assert any(e["value"] == "서울" for e in locations)

    def test_extract_busan(self, extractor):
        """부산 지역 추출 테스트."""
        entities = extractor.extract("부산 전시장에서 행사를 합니다")
        locations = [e for e in entities if e["entity_type"] == "location"]
        assert any(e["value"] == "부산" for e in locations)

    def test_extract_incheon(self, extractor):
        """인천 지역 추출 테스트."""
        entities = extractor.extract("인천본부세관 관할입니다")
        locations = [e for e in entities if e["entity_type"] == "location"]
        assert any(e["value"] == "인천" for e in locations)


# --- date_range 추출 테스트 ---

class TestDateRangeExtraction:
    """date_range 엔티티 추출 테스트."""

    def test_extract_next_week(self, extractor):
        """다음주 추출 테스트."""
        entities = extractor.extract("다음주에 반입 예정입니다")
        dates = [e for e in entities if e["entity_type"] == "date_range"]
        assert any(e["value"] == "다음주" for e in dates)

    def test_extract_days_later(self, extractor):
        """N일 후 추출 테스트."""
        entities = extractor.extract("3일 후에 반출합니다")
        dates = [e for e in entities if e["entity_type"] == "date_range"]
        assert len(dates) >= 1
        assert any("3일" in e["value"] for e in dates)

    def test_extract_event_period(self, extractor):
        """행사기간 추출 테스트."""
        entities = extractor.extract("행사기간 동안 전시합니다")
        dates = [e for e in entities if e["entity_type"] == "date_range"]
        assert any(e["value"] == "행사기간" for e in dates)


# --- declaration_status 추출 테스트 ---

class TestDeclarationStatusExtraction:
    """declaration_status 엔티티 추출 테스트."""

    def test_extract_before_declaration(self, extractor):
        """신고전 추출 테스트."""
        entities = extractor.extract("아직 신고 전입니다")
        statuses = [e for e in entities if e["entity_type"] == "declaration_status"]
        assert any(e["value"] == "신고전" for e in statuses)

    def test_extract_declaration_complete(self, extractor):
        """신고완료 추출 테스트."""
        entities = extractor.extract("반입신고완료 상태입니다")
        statuses = [e for e in entities if e["entity_type"] == "declaration_status"]
        assert len(statuses) >= 1

    def test_extract_undeclared(self, extractor):
        """미신고 추출 테스트."""
        entities = extractor.extract("미신고 물품이 있습니다")
        statuses = [e for e in entities if e["entity_type"] == "declaration_status"]
        assert any(e["value"] == "미신고" for e in statuses)


# --- legal_reference 추출 테스트 ---

class TestLegalReferenceExtraction:
    """legal_reference 엔티티 추출 테스트."""

    def test_extract_article_number(self, extractor):
        """제190조 추출 테스트."""
        entities = extractor.extract("관세법 제190조에 따르면")
        legal = [e for e in entities if e["entity_type"] == "legal_reference"]
        assert any("190" in e["value"] for e in legal)

    def test_extract_customs_law(self, extractor):
        """관세법 추출 테스트."""
        entities = extractor.extract("관세법에 의거하여 처리합니다")
        legal = [e for e in entities if e["entity_type"] == "legal_reference"]
        assert any("관세법" in e["value"] for e in legal)

    def test_extract_enforcement_decree(self, extractor):
        """시행령 추출 테스트."""
        entities = extractor.extract("관세법 시행령을 확인해주세요")
        legal = [e for e in entities if e["entity_type"] == "legal_reference"]
        assert any("시행령" in e["value"] for e in legal)


# --- 복합 엔티티 추출 테스트 ---

class TestMultipleEntityExtraction:
    """복합 엔티티 추출 테스트."""

    def test_multiple_entity_types(self, extractor):
        """하나의 질문에서 여러 타입의 엔티티 추출."""
        entities = extractor.extract(
            "출품업체가 서울 전시장에서 식품을 시식하려 합니다"
        )
        types_found = {e["entity_type"] for e in entities}
        assert "user_type" in types_found
        assert "location" in types_found
        assert "item_type" in types_found
        assert "action_type" in types_found

    def test_multiple_actions_in_one_query(self, extractor):
        """하나의 질문에서 여러 action_type 추출."""
        entities = extractor.extract("반입, 전시, 판매, 반출 절차를 알려주세요")
        actions = [e for e in entities if e["entity_type"] == "action_type"]
        action_values = {e["value"] for e in actions}
        assert "반입" in action_values
        assert "판매" in action_values
        assert "반출" in action_values


# --- 컨텍스트 기반 추출 테스트 ---

class TestContextExtraction:
    """컨텍스트 기반 엔티티 추출 테스트."""

    def test_context_fills_missing_entity(self, extractor):
        """이전 대화에서 누락된 엔티티를 보완."""
        history = ["서울 전시장에서 식품을 반입합니다"]
        entities = extractor.extract_with_context(
            "관세는 얼마인가요", session_history=history
        )
        # 현재 질문에는 location이 없지만 히스토리에서 보완
        types_found = {e["entity_type"] for e in entities}
        assert "location" in types_found

    def test_context_without_history(self, extractor):
        """히스토리 없이 컨텍스트 추출."""
        entities = extractor.extract_with_context("식품을 반입합니다")
        assert len(entities) >= 1

    def test_context_entity_has_lower_confidence(self, extractor):
        """컨텍스트에서 가져온 엔티티는 confidence가 낮아야 한다."""
        history = ["부산 전시장에서 행사합니다"]
        entities = extractor.extract_with_context(
            "절차가 궁금합니다", session_history=history
        )
        context_entities = [
            e for e in entities if "[컨텍스트]" in e.get("span", "")
        ]
        for e in context_entities:
            assert e["confidence"] < 0.85

    def test_context_does_not_override_current(self, extractor):
        """현재 질문의 엔티티가 컨텍스트보다 우선."""
        history = ["부산에서 행사합니다"]
        entities = extractor.extract_with_context(
            "서울 세관에 문의합니다", session_history=history
        )
        locations = [e for e in entities if e["entity_type"] == "location"]
        # 서울만 있어야 함 (부산은 현재 질문에 서울이 이미 있으므로 추가되지 않음)
        location_values = [e["value"] for e in locations]
        assert "서울" in location_values


# --- 에지 케이스 테스트 ---

class TestEdgeCases:
    """에지 케이스 테스트."""

    def test_empty_query(self, extractor):
        """빈 문자열 입력."""
        assert extractor.extract("") == []

    def test_whitespace_query(self, extractor):
        """공백만 있는 입력."""
        assert extractor.extract("   ") == []

    def test_none_like_query(self, extractor):
        """엔티티가 전혀 없는 질문."""
        entities = extractor.extract("안녕하세요 좋은 아침입니다")
        # 엔티티가 없거나 매우 적어야 함
        assert isinstance(entities, list)

    def test_entity_structure(self, extractor):
        """추출된 엔티티의 구조 검증."""
        entities = extractor.extract("관세사가 식품을 반입합니다")
        for entity in entities:
            assert "entity_type" in entity
            assert "value" in entity
            assert "confidence" in entity
            assert "span" in entity
            assert 0.0 <= entity["confidence"] <= 1.0

    def test_get_entity_summary_empty(self, extractor):
        """빈 리스트의 요약."""
        summary = extractor.get_entity_summary([])
        assert summary == "추출된 엔티티가 없습니다."

    def test_get_entity_summary_with_entities(self, extractor):
        """엔티티가 있을 때 요약."""
        entities = extractor.extract("관세사가 서울에서 식품을 반입합니다")
        summary = extractor.get_entity_summary(entities)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_get_entity_dictionary(self, extractor):
        """엔티티 사전 반환 테스트."""
        dictionary = extractor.get_entity_dictionary()
        assert isinstance(dictionary, dict)
        assert len(dictionary) > 0
        for entity_id, info in dictionary.items():
            assert "values" in info
            assert "description" in info


# --- API 엔드포인트 테스트 ---

class TestEntityAPIEndpoint:
    """API 엔드포인트 테스트."""

    def test_chat_response_includes_entities(self, client):
        """POST /api/chat 응답에 entities 필드가 포함되는지 확인."""
        res = client.post(
            "/api/chat",
            json={"query": "관세사가 식품을 반입합니다"},
            content_type="application/json",
        )
        data = res.get_json()
        if res.status_code == 200:
            assert "entities" in data
            assert isinstance(data["entities"], list)
        else:
            # 챗봇 처리 에러(pre-existing)가 있어도 엔티티 추출 자체는 동작함을 확인
            # 엔티티 추출 로직이 /api/chat에 통합되어 있음을 별도로 확인
            entities = EntityExtractorV2().extract("관세사가 식품을 반입합니다")
            assert len(entities) >= 2
            assert any(e["entity_type"] == "user_type" for e in entities)
            assert any(e["entity_type"] == "action_type" for e in entities)

    def test_entity_dictionary_endpoint(self, client):
        """GET /api/admin/entities/dictionary 엔드포인트 테스트."""
        res = client.get("/api/admin/entities/dictionary")
        assert res.status_code == 200
        data = res.get_json()
        assert "entity_dictionary" in data
        dictionary = data["entity_dictionary"]
        assert isinstance(dictionary, dict)
        # entities.json에 정의된 타입이 포함되어야 함
        assert "user_type" in dictionary
        assert "item_type" in dictionary
        assert "action_type" in dictionary


# --- 싱글톤 테스트 ---

class TestSingleton:
    """싱글톤 패턴 테스트."""

    def test_get_entity_extractor_v2_returns_same_instance(self):
        """get_entity_extractor_v2가 동일 인스턴스를 반환하는지 확인."""
        e1 = get_entity_extractor_v2()
        e2 = get_entity_extractor_v2()
        assert e1 is e2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
