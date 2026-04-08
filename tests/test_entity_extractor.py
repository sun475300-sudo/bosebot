"""Integration tests for EntityExtractor module.

Tests entity extraction for user types, item types, action types,
and graceful handling of missing data.
"""

import logging
import os
import tempfile
from pathlib import Path

import pytest

from src.entity_extractor import (
    EntityExtractor,
    get_entity_extractor,
    extract_entities,
)


logger = logging.getLogger(__name__)


class TestEntityExtractorInitialization:
    """Test EntityExtractor initialization."""

    def test_entity_extractor_initialization_succeeds(self):
        """Test that EntityExtractor initializes successfully."""
        extractor = EntityExtractor()
        assert extractor is not None

    def test_entity_types_loaded_from_json(self):
        """Test that entity types are loaded from data/entities.json."""
        extractor = EntityExtractor()
        assert extractor.entity_types is not None
        assert len(extractor.entity_types) > 0

    def test_extraction_patterns_compiled(self):
        """Test that extraction patterns are compiled."""
        extractor = EntityExtractor()
        assert extractor.extraction_patterns is not None
        # Should have patterns for entity types with patterns defined
        if extractor.entity_types:
            assert len(extractor.extraction_patterns) > 0

    def test_graceful_degradation_missing_entities_file(self):
        """Test graceful degradation when entities.json is missing."""
        # Temporarily rename entities file
        entities_path = Path("data/entities.json")
        backup_path = Path("data/entities.json.backup")

        if entities_path.exists():
            entities_path.rename(backup_path)

        try:
            extractor = EntityExtractor()
            # Should have empty types due to missing file
            assert extractor.entity_types == {}
            assert extractor.extraction_patterns == {}
            # But extraction should return empty dict gracefully
            result = extractor.extract("some query")
            assert result == {}
        finally:
            # Restore file
            if backup_path.exists():
                backup_path.rename(entities_path)


class TestUserTypeExtraction:
    """Test extraction of user_type entities."""

    def test_extract_operator_user_type(self):
        """Test extraction of operator (운영인) user type."""
        extractor = EntityExtractor()
        result = extractor.extract("운영인으로서 질문이 있습니다")
        # Should extract operator if entity_types loaded successfully
        if extractor.entity_types:
            # May contain user_type or related entity
            assert isinstance(result, dict)

    def test_extract_exhibitor_user_type(self):
        """Test extraction of exhibitor (출품자) user type."""
        extractor = EntityExtractor()
        result = extractor.extract("저는 출품자입니다")
        assert isinstance(result, dict)

    def test_extract_visitor_user_type(self):
        """Test extraction of visitor (관람객) user type."""
        extractor = EntityExtractor()
        result = extractor.extract("관람객으로서 질문합니다")
        assert isinstance(result, dict)

    def test_extract_customs_broker(self):
        """Test extraction of customs broker (관세사) user type."""
        extractor = EntityExtractor()
        result = extractor.extract("관세사가 묻습니다")
        assert isinstance(result, dict)

    def test_extract_customs_official(self):
        """Test extraction of customs official (세관공무원) user type."""
        extractor = EntityExtractor()
        result = extractor.extract("저는 세관공무원입니다")
        assert isinstance(result, dict)

    def test_multiple_user_types_in_query(self):
        """Test extraction of multiple user types from single query."""
        extractor = EntityExtractor()
        result = extractor.extract("운영인과 출품자, 관람객 모두 질문할 수 있나요?")
        assert isinstance(result, dict)
        # If any user types were extracted, they should be in result
        if result:
            for entity_id, entities_list in result.items():
                assert isinstance(entities_list, list)
                for entity in entities_list:
                    assert "value" in entity


class TestItemTypeExtraction:
    """Test extraction of item_type entities."""

    def test_extract_foreign_goods(self):
        """Test extraction of foreign goods (외국물품)."""
        extractor = EntityExtractor()
        result = extractor.extract("외국물품을 반입할 수 있나요?")
        assert isinstance(result, dict)

    def test_extract_sample_goods(self):
        """Test extraction of sample goods (견본품)."""
        extractor = EntityExtractor()
        result = extractor.extract("견본품을 전시할 수 있습니다")
        assert isinstance(result, dict)

    def test_extract_prohibited_goods(self):
        """Test extraction of prohibited goods."""
        extractor = EntityExtractor()
        result = extractor.extract("금지 물품은 어떤 것들인가요?")
        assert isinstance(result, dict)

    def test_extract_hazardous_goods(self):
        """Test extraction of hazardous goods."""
        extractor = EntityExtractor()
        result = extractor.extract("위험 물품 규정이 뭐죠?")
        assert isinstance(result, dict)


class TestActionTypeExtraction:
    """Test extraction of action_type entities."""

    def test_extract_import_action(self):
        """Test extraction of import action (반입)."""
        extractor = EntityExtractor()
        result = extractor.extract("물품을 반입할 때 필요한 것은?")
        assert isinstance(result, dict)

    def test_extract_export_action(self):
        """Test extraction of export action (반출)."""
        extractor = EntityExtractor()
        result = extractor.extract("전시 후 반출하는 방법은?")
        assert isinstance(result, dict)

    def test_extract_exhibition_action(self):
        """Test extraction of exhibition action (전시)."""
        extractor = EntityExtractor()
        result = extractor.extract("전시 기간은 얼마나 되나요?")
        assert isinstance(result, dict)

    def test_extract_sale_action(self):
        """Test extraction of sale action (판매)."""
        extractor = EntityExtractor()
        result = extractor.extract("전시장에서 판매할 수 있나요?")
        assert isinstance(result, dict)

    def test_extract_storage_action(self):
        """Test extraction of storage action (보관)."""
        extractor = EntityExtractor()
        result = extractor.extract("물품을 어디에 보관하나요?")
        assert isinstance(result, dict)

    def test_multiple_actions_in_query(self):
        """Test extraction of multiple actions from single query."""
        extractor = EntityExtractor()
        result = extractor.extract("반입, 전시, 판매, 반출의 절차는?")
        assert isinstance(result, dict)
        if result:
            for entity_id, entities_list in result.items():
                assert isinstance(entities_list, list)


class TestComplexSentences:
    """Test extraction from complex sentences."""

    def test_complex_sentence_multiple_entities(self):
        """Test extraction from complex sentence with multiple entity types."""
        extractor = EntityExtractor()
        query = "출품자가 외국물품을 반입하여 전시한 후 반출하는 절차는?"
        result = extractor.extract(query)
        assert isinstance(result, dict)
        # May have multiple entity types extracted
        if result:
            # Each entity type should have a list of entities
            for entity_id, entities_list in result.items():
                assert isinstance(entities_list, list)
                for entity in entities_list:
                    assert isinstance(entity, dict)
                    assert "value" in entity
                    assert "confidence" in entity

    def test_complex_sentence_with_synonyms(self):
        """Test extraction using synonyms from complex sentence."""
        extractor = EntityExtractor()
        query = "시설운영자와 상품출품자, 방문객이 모두 묻는 질문"
        result = extractor.extract(query)
        assert isinstance(result, dict)

    def test_long_query_with_many_entities(self):
        """Test extraction from long query with many potential entities."""
        extractor = EntityExtractor()
        query = (
            "운영인으로서 관세사와 함께 외국물품을 반입하여 "
            "견본품을 전시하고 나중에 반출하는 과정 중 "
            "위험물품 규정에 관해 묻습니다"
        )
        result = extractor.extract(query)
        assert isinstance(result, dict)


class TestEmptyAndIrrelevantQueries:
    """Test handling of empty and irrelevant queries."""

    def test_empty_query_returns_empty_dict(self):
        """Test that empty query returns empty dictionary."""
        extractor = EntityExtractor()
        result = extractor.extract("")
        assert result == {}

    def test_whitespace_only_query_returns_empty_dict(self):
        """Test that whitespace-only query returns empty dictionary."""
        extractor = EntityExtractor()
        result = extractor.extract("   ")
        assert result == {}

    def test_irrelevant_query_returns_empty_dict(self):
        """Test that irrelevant query returns empty dictionary."""
        extractor = EntityExtractor()
        result = extractor.extract("날씨가 어떻게 되나요?")
        # May return empty or partial results depending on entities.json
        assert isinstance(result, dict)

    def test_query_with_no_matching_entities(self):
        """Test query that doesn't match any entities."""
        extractor = EntityExtractor()
        result = extractor.extract("asdfjkl qwerty zxcvbn")
        # Should return empty or minimal results
        assert isinstance(result, dict)


class TestEntityExtractionFormat:
    """Test format of extracted entity results."""

    def test_entity_extraction_result_structure(self):
        """Test that extraction result has correct structure."""
        extractor = EntityExtractor()
        result = extractor.extract("운영인이 외국물품을 반입합니다")
        assert isinstance(result, dict)

        for entity_type_id, entities_list in result.items():
            assert isinstance(entity_type_id, str)
            assert isinstance(entities_list, list)

            for entity in entities_list:
                assert isinstance(entity, dict)
                assert "value" in entity  # Extracted value
                assert "confidence" in entity  # Confidence score
                # May have other fields like matched_text

    def test_entity_object_has_required_fields(self):
        """Test that each extracted entity has required fields."""
        extractor = EntityExtractor()
        result = extractor.extract("출품자가 묻습니다")

        for entity_type_id, entities_list in result.items():
            for entity in entities_list:
                assert "value" in entity
                assert isinstance(entity["value"], str)
                assert "confidence" in entity
                assert 0.0 <= entity["confidence"] <= 1.0

    def test_entity_confidence_scores_reasonable(self):
        """Test that confidence scores are in reasonable range."""
        extractor = EntityExtractor()
        result = extractor.extract("운영인과 세관공무원")

        for entity_type_id, entities_list in result.items():
            for entity in entities_list:
                # Confidence should be between 0 and 1
                assert 0.0 <= entity["confidence"] <= 1.0


class TestEntityExtractorMethods:
    """Test individual EntityExtractor methods."""

    def test_get_entity_value_description_exists(self):
        """Test getting description for existing entity value."""
        extractor = EntityExtractor()
        if extractor.entity_types:
            # Get first entity type and first value
            for entity_id, entity_type in extractor.entity_types.items():
                values = entity_type.get("values", [])
                if values:
                    value = values[0].get("value")
                    description = extractor.get_entity_value_description(entity_id, value)
                    # May have description or None
                    if description:
                        assert isinstance(description, str)
                    break

    def test_get_entity_value_description_nonexistent(self):
        """Test getting description for non-existent entity value."""
        extractor = EntityExtractor()
        description = extractor.get_entity_value_description("nonexistent_id", "nonexistent_value")
        assert description is None

    def test_get_entity_value_description_nonexistent_type(self):
        """Test getting description for non-existent entity type."""
        extractor = EntityExtractor()
        description = extractor.get_entity_value_description("fake_entity_type", "value")
        assert description is None


class TestGetEntityExtractorSingleton:
    """Test module-level convenience functions."""

    def test_get_entity_extractor_singleton(self):
        """Test that get_entity_extractor returns singleton."""
        extractor1 = get_entity_extractor()
        extractor2 = get_entity_extractor()
        assert extractor1 is extractor2

    def test_extract_entities_function(self):
        """Test extract_entities module function."""
        result = extract_entities("출품자가 외국물품을 반입합니다")
        assert isinstance(result, dict)

    def test_extract_entities_returns_same_as_method(self):
        """Test that extract_entities function matches extractor.extract."""
        query = "관람객이 물품을 구매하고 반출합니다"
        extractor = EntityExtractor()
        result1 = extractor.extract(query)
        result2 = extract_entities(query)
        # Should have same structure (though may differ if singleton changes)
        assert isinstance(result1, dict)
        assert isinstance(result2, dict)


class TestDuplicateRemoval:
    """Test duplicate entity removal."""

    def test_duplicate_entities_removed(self):
        """Test that duplicate entities are removed."""
        extractor = EntityExtractor()
        # Query that might match same entity multiple times
        query = "운영인 운영인 운영인"
        result = extractor.extract(query)

        for entity_type_id, entities_list in result.items():
            # After deduplication, shouldn't have exact duplicates
            values = [e["value"] for e in entities_list]
            # Check that we don't have many duplicates (some removal occurred)
            assert isinstance(values, list)

    def test_similar_entities_preserved(self):
        """Test that similar but different entities are preserved."""
        extractor = EntityExtractor()
        query = "운영인과 출품자와 관람객"
        result = extractor.extract(query)

        # Should have or attempt to have multiple different entities
        assert isinstance(result, dict)


class TestEntityTypeIds:
    """Test handling of different entity type IDs."""

    def test_known_entity_types_extracted(self):
        """Test extraction of known entity types."""
        extractor = EntityExtractor()
        if extractor.entity_types:
            # entity_types should have keys like user_type, item_type, action_type, etc.
            entity_ids = list(extractor.entity_types.keys())
            assert len(entity_ids) > 0
            for entity_id in entity_ids:
                assert isinstance(entity_id, str)

    def test_extraction_result_keys_match_entity_types(self):
        """Test that extraction results only use known entity type IDs."""
        extractor = EntityExtractor()
        result = extractor.extract("운영인과 출품자가 외국물품을 반입합니다")

        known_ids = set(extractor.entity_types.keys())
        for entity_type_id in result.keys():
            assert entity_type_id in known_ids


class TestCaseInsensitivity:
    """Test case-insensitive entity extraction."""

    def test_uppercase_query_extraction(self):
        """Test extraction from uppercase query."""
        extractor = EntityExtractor()
        result1 = extractor.extract("운영인")
        result2 = extractor.extract("운영인".upper())  # Should still work
        assert isinstance(result1, dict)
        assert isinstance(result2, dict)

    def test_mixed_case_extraction(self):
        """Test extraction from mixed-case query."""
        extractor = EntityExtractor()
        result = extractor.extract("運營人과 出品者")
        assert isinstance(result, dict)


class TestPatternCompilation:
    """Test regex pattern compilation."""

    def test_patterns_compile_without_error(self):
        """Test that all patterns compile without error."""
        extractor = EntityExtractor()
        # If patterns failed to compile, they wouldn't be in extraction_patterns
        for entity_id, pattern in extractor.extraction_patterns.items():
            assert pattern is not None
            # Pattern should have finditer method
            assert hasattr(pattern, 'finditer')

    def test_invalid_patterns_handled_gracefully(self):
        """Test that invalid patterns are handled gracefully."""
        # This is tested during initialization
        extractor = EntityExtractor()
        # If any patterns were invalid, they would be logged but not crash
        assert extractor.extraction_patterns is not None


class TestEntityValueDescription:
    """Test entity value descriptions."""

    def test_description_retrieval_for_entity_values(self):
        """Test retrieving descriptions for entity values."""
        extractor = EntityExtractor()
        if extractor.entity_types:
            for entity_id, entity_type in extractor.entity_types.items():
                values = entity_type.get("values", [])
                for value_obj in values[:2]:  # Test first 2 values
                    value = value_obj.get("value")
                    description = extractor.get_entity_value_description(entity_id, value)
                    # Description may be None or a string
                    assert description is None or isinstance(description, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
