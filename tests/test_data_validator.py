"""데이터 정합성 검증 테스트."""

import pytest
from src.data_validator import (
    validate_faq_legal_references,
    validate_faq_categories,
    validate_escalation_targets,
    validate_faq_keywords_not_empty,
    run_all_validations,
)


class TestValidateFaqLegalReferences:
    """FAQ 법령 근거 정합성 검증 테스트."""

    def test_no_errors(self):
        errors = validate_faq_legal_references()
        assert errors == [], f"법령 근거 정합성 오류 발견: {errors}"


class TestValidateFaqCategories:
    """FAQ 카테고리 커버리지 검증 테스트."""

    def test_all_categories_covered(self):
        errors = validate_faq_categories()
        assert errors == [], f"카테고리 커버리지 오류 발견: {errors}"


class TestValidateEscalationTargets:
    """에스컬레이션 target 정합성 검증 테스트."""

    def test_all_targets_valid(self):
        errors = validate_escalation_targets()
        assert errors == [], f"에스컬레이션 target 오류 발견: {errors}"


class TestValidateFaqKeywords:
    """FAQ 키워드 비어있지 않은지 검증 테스트."""

    def test_no_empty_keywords(self):
        errors = validate_faq_keywords_not_empty()
        assert errors == [], f"키워드 누락 오류 발견: {errors}"


class TestRunAllValidations:
    """전체 검증 통합 테스트."""

    def test_all_pass(self):
        results = run_all_validations()
        all_errors = []
        for name, errors in results.items():
            for err in errors:
                all_errors.append(f"[{name}] {err}")
        assert all_errors == [], f"정합성 검증 실패:\n" + "\n".join(all_errors)
