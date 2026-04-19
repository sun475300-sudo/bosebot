"""VariantMatcher 테스트 모듈."""

import json
import os
import tempfile

import pytest

from src.variant_matcher import VariantMatcher


@pytest.fixture
def sample_variants_data():
    """테스트용 변형 데이터."""
    return {
        "version": "1.0.0",
        "description": "테스트용 질문 변형 데이터셋",
        "variants": [
            {
                "faq_id": "A",
                "original_question": "보세전시장이 무엇인가요?",
                "variants": [
                    "보세전시장이 뭔가요?",
                    "보세전시장 정의가 뭐예요?",
                    "보세전시장이란?",
                    "보세전시장 설명해주세요",
                    "보세전시장이 뭐야",
                ],
            },
            {
                "faq_id": "B",
                "original_question": "보세전시장에 물품을 반입하거나 반출하려면 신고가 필요한가요?",
                "variants": [
                    "물품 반출입할 때 신고해야 돼?",
                    "보세전시장 반입 반출 신고 필요?",
                    "전시장에 물건 넣고 빼려면 어떻게 하나요?",
                    "반출입신고 안 하면 안 되나요?",
                    "물품 반입할 때 세관 신고 어디서 해야 해요?",
                ],
            },
            {
                "faq_id": "T",
                "original_question": "보세전시장과 보세창고는 어떻게 다른가요?",
                "variants": [
                    "보세전시장이랑 보세창고 차이가 뭐야?",
                    "보세전시장 보세창고 차이 알려주세요",
                    "전시장과 창고 뭐가 다른가요?",
                    "보세전시장 보세창고 비교 어떻게 하나요?",
                    "보세전시장 보세창고 구분 어디서 확인해요?",
                ],
            },
        ],
    }


@pytest.fixture
def variants_file(sample_variants_data, tmp_path):
    """테스트용 JSON 파일을 생성합니다."""
    filepath = tmp_path / "question_variants.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sample_variants_data, f, ensure_ascii=False)
    return str(filepath)


@pytest.fixture
def loaded_matcher(variants_file):
    """변형 데이터가 로드된 VariantMatcher를 반환합니다."""
    matcher = VariantMatcher()
    matcher.load_variants(variants_file)
    return matcher


class TestLoadVariants:
    """변형 데이터 로딩 테스트."""

    def test_load_variants_success(self, variants_file):
        """JSON 파일을 정상적으로 로드합니다."""
        matcher = VariantMatcher()
        result = matcher.load_variants(variants_file)
        assert result is not None
        assert result["version"] == "1.0.0"
        assert len(result["variants"]) == 3

    def test_load_variants_file_not_found(self):
        """존재하지 않는 파일 로드 시 FileNotFoundError 발생."""
        matcher = VariantMatcher()
        with pytest.raises(FileNotFoundError):
            matcher.load_variants("/nonexistent/path.json")

    def test_load_variants_invalid_json(self, tmp_path):
        """유효하지 않은 JSON 파일 로드 시 JSONDecodeError 발생."""
        filepath = tmp_path / "invalid.json"
        filepath.write_text("not valid json {{{", encoding="utf-8")
        matcher = VariantMatcher()
        with pytest.raises(json.JSONDecodeError):
            matcher.load_variants(str(filepath))

    def test_load_variants_builds_index(self, loaded_matcher):
        """로드 후 인덱스가 구축되었는지 확인."""
        assert loaded_matcher._is_indexed is True
        assert len(loaded_matcher._documents) > 0
        assert len(loaded_matcher._tfidf_matrix) > 0


class TestFindMatch:
    """질문 매칭 테스트."""

    def test_match_original_question(self, loaded_matcher):
        """원본 질문과 정확히 일치하는 쿼리로 매칭."""
        result = loaded_matcher.find_match("보세전시장이 무엇인가요?")
        assert result is not None
        assert result["faq_id"] == "A"
        assert result["score"] > 0.6

    def test_match_variant_question(self, loaded_matcher):
        """변형 질문으로 매칭."""
        result = loaded_matcher.find_match("보세전시장이 뭔가요?")
        assert result is not None
        assert result["faq_id"] == "A"

    def test_match_variant_colloquial(self, loaded_matcher):
        """구어체 변형으로 매칭."""
        result = loaded_matcher.find_match("보세전시장이 뭐야")
        assert result is not None
        assert result["faq_id"] == "A"

    def test_match_different_faq(self, loaded_matcher):
        """다른 FAQ의 변형 질문으로 매칭."""
        result = loaded_matcher.find_match("보세전시장 반입 반출 신고 필요?")
        assert result is not None
        assert result["faq_id"] == "B"

    def test_match_warehouse_comparison(self, loaded_matcher):
        """보세창고 비교 질문 매칭."""
        result = loaded_matcher.find_match("보세전시장이랑 보세창고 차이가 뭐야?")
        assert result is not None
        assert result["faq_id"] == "T"

    def test_no_match_below_threshold(self, loaded_matcher):
        """임계값 미만인 쿼리는 None 반환."""
        result = loaded_matcher.find_match("오늘 날씨 어때?", threshold=0.6)
        assert result is None

    def test_no_match_empty_query(self, loaded_matcher):
        """빈 쿼리는 None 반환."""
        result = loaded_matcher.find_match("")
        assert result is None

    def test_match_without_loading(self):
        """로드 전 매칭 시 None 반환."""
        matcher = VariantMatcher()
        result = matcher.find_match("보세전시장이 무엇인가요?")
        assert result is None

    def test_match_result_structure(self, loaded_matcher):
        """매칭 결과의 구조를 확인."""
        result = loaded_matcher.find_match("보세전시장이 무엇인가요?")
        assert result is not None
        assert "faq_id" in result
        assert "matched_question" in result
        assert "score" in result
        assert isinstance(result["score"], float)


class TestGetAllVariants:
    """변형 질문 조회 테스트."""

    def test_get_variants_existing_faq(self, loaded_matcher):
        """존재하는 FAQ ID의 변형 질문 조회."""
        variants = loaded_matcher.get_all_variants("A")
        assert len(variants) == 5
        assert "보세전시장이 뭔가요?" in variants

    def test_get_variants_nonexistent_faq(self, loaded_matcher):
        """존재하지 않는 FAQ ID는 빈 리스트 반환."""
        variants = loaded_matcher.get_all_variants("ZZ")
        assert variants == []

    def test_get_variants_without_loading(self):
        """로드 전 조회 시 빈 리스트 반환."""
        matcher = VariantMatcher()
        variants = matcher.get_all_variants("A")
        assert variants == []


class TestAddVariant:
    """변형 질문 추가 테스트."""

    def test_add_variant_success(self, loaded_matcher):
        """새 변형 질문 추가 성공."""
        result = loaded_matcher.add_variant("A", "보세전시장 개념이 뭐지?")
        assert result is True
        variants = loaded_matcher.get_all_variants("A")
        assert "보세전시장 개념이 뭐지?" in variants
        assert len(variants) == 6

    def test_add_variant_duplicate(self, loaded_matcher):
        """이미 존재하는 변형은 중복 추가되지 않음."""
        loaded_matcher.add_variant("A", "보세전시장이 뭔가요?")
        variants = loaded_matcher.get_all_variants("A")
        assert variants.count("보세전시장이 뭔가요?") == 1

    def test_add_variant_nonexistent_faq(self, loaded_matcher):
        """존재하지 않는 FAQ에는 추가 실패."""
        result = loaded_matcher.add_variant("ZZ", "테스트 질문")
        assert result is False

    def test_add_variant_rebuilds_index(self, loaded_matcher):
        """변형 추가 후 인덱스 재구축 확인."""
        original_doc_count = len(loaded_matcher._documents)
        loaded_matcher.add_variant("A", "보세전시장 개념이 뭐지?")
        assert len(loaded_matcher._documents) == original_doc_count + 1

    def test_add_variant_without_loading(self):
        """로드 전 추가 시 실패."""
        matcher = VariantMatcher()
        result = matcher.add_variant("A", "테스트")
        assert result is False


class TestWithRealData:
    """실제 question_variants.json 파일로 테스트."""

    @pytest.fixture
    def real_matcher(self):
        """실제 데이터 파일로 VariantMatcher를 로드합니다."""
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "question_variants.json",
        )
        if not os.path.exists(data_path):
            pytest.skip("question_variants.json not found")
        matcher = VariantMatcher()
        matcher.load_variants(data_path)
        return matcher

    def test_real_data_loads_30_faqs(self, real_matcher):
        """실제 데이터에 30개 FAQ가 포함되어 있는지 확인."""
        assert len(real_matcher.variants_data["variants"]) == 30

    def test_real_data_each_has_5_variants(self, real_matcher):
        """각 FAQ에 5개 변형이 있는지 확인."""
        for item in real_matcher.variants_data["variants"]:
            assert len(item["variants"]) == 5, (
                f"FAQ {item['faq_id']} has {len(item['variants'])} variants, expected 5"
            )
