"""특허 질문 답변 품질 회귀 테스트.

다음 3가지 버그가 재발하지 않도록 보호한다:
  1. spell_corrector가 '신청/지정/등록' 같은 핵심 절차어를 자동 변환하던 문제
  2. synonym_resolver의 단일 음절 매핑(사/팔/빼/벌)이 부분 문자열 매치로 오작동하던 문제
  3. korean_tokenizer DOMAIN_TERMS에 특허 복합명사가 빠져 분리되던 문제
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from src.spell_corrector import correct_query, KNOWN_TERMS
from src.synonym_resolver import expand_query, SYNONYMS
from src.korean_tokenizer import KoreanTokenizer
from src.classifier import get_primary_category


# ---- BUG A: spell_corrector ---------------------------------------------

@pytest.mark.parametrize("term", ["신청", "지정", "등록", "출원"])
def test_procedural_terms_are_protected_from_spell_correction(term):
    """핵심 절차어는 KNOWN_TERMS에 등록되어 자동 교정 대상에서 제외."""
    assert term in KNOWN_TERMS, f"{term!r} must be in KNOWN_TERMS"


def test_patent_application_query_is_not_mangled():
    """'특허 신청'이 '특허 신고'로 잘못 교정되지 않아야 한다."""
    corrected, corrections = correct_query("특허 신청 어떻게 하나요")
    assert "신청" in corrected, f"'신청' must survive: got {corrected!r}"
    assert "신고" not in corrected.split(), \
        f"'신청' must not be auto-corrected to '신고': got {corrected!r}"


def test_jijung_kigan_query_is_not_mangled():
    """'지정'이 '규정'으로 잘못 교정되지 않아야 한다."""
    corrected, _ = correct_query("지정 기간 얼마나")
    assert "지정" in corrected, f"'지정' must survive: got {corrected!r}"
    assert "규정" not in corrected.split(), \
        f"'지정' must not be auto-corrected to '규정': got {corrected!r}"


# ---- BUG B: synonym_resolver --------------------------------------------

@pytest.mark.parametrize("bad_key", ["사", "팔", "빼", "벌"])
def test_no_single_syllable_synonyms(bad_key):
    """단일 음절 동의어 키는 부분 문자열 오작동을 일으키므로 금지."""
    assert bad_key not in SYNONYMS, \
        f"{bad_key!r} is too short and matches inside other words"


def test_sayoo_does_not_pull_in_purchase():
    """'특허 취소 사유'에 '구매' 동의어가 끼어들지 않아야 한다."""
    expanded = expand_query("특허 취소 사유는 무엇인가요")
    assert "구매" not in expanded, \
        f"'사유' should not pull in '구매': got {expanded!r}"


def test_kaengshin_still_appends_yeonjang():
    """'갱신'은 여전히 '연장'을 부착해야 LICENSE 키워드 신호가 강해진다."""
    expanded = expand_query("특허 갱신 가능한가요")
    assert "갱신" in expanded
    assert "연장" in expanded


# ---- BUG C: korean_tokenizer --------------------------------------------

@pytest.mark.parametrize("term", [
    "특허", "특허기간", "특허신청", "특허장소",
    "특허취소", "특허연장", "특허신청서", "설치특허",
])
def test_patent_compounds_in_tokenizer_domain_terms(term):
    """특허 핵심 복합명사는 토크나이저 도메인 사전에 포함되어야 한다."""
    assert term in KoreanTokenizer.DOMAIN_TERMS, \
        f"{term!r} must be in DOMAIN_TERMS"


def test_tokenizer_keeps_teukheo_kigan_intact():
    tk = KoreanTokenizer()
    tokens = tk.tokenize("보세전시장 특허기간은 어떻게 되나요")
    assert "특허기간" in tokens, f"got {tokens!r}"


# ---- 통합 (E2E) — 카테고리 분류 골든셋 ----------------------------------

PATENT_GOLDEN_CASES = [
    ("특허 신청 어떻게 하나요",                                     "LICENSE"),
    ("특허 신청 비용이 드나요",                                     "LICENSE"),
    ("지정 기간이 얼마나 되나요",                                   "LICENSE"),
    ("특허 취소 사유는 무엇인가요",                                 "PENALTIES"),
    ("보세전시장 특허기간은 어떻게 되나요",                         "LICENSE"),
    ("특허 갱신 가능한가요",                                        "LICENSE"),
    ("등록 신청 어떻게",                                            "LICENSE"),
    ("보세전시장 설치·운영 특허를 받으려면 어디를 봐야 하나요",     "LICENSE"),
    ("특허 연장이 가능한가요",                                      "LICENSE"),
    ("특허 신청 시 어떤 서류가 필요한가요",                         "DOCUMENTS"),
    ("보세전시장 특허 관련 담당 부서가 어디인가요",                 "CONTACT"),
]


@pytest.mark.parametrize("query,expected_cat", PATENT_GOLDEN_CASES)
def test_patent_query_category_routing(query, expected_cat):
    """특허 관련 질문이 올바른 카테고리로 분류되는지 E2E 검증."""
    corrected, _ = correct_query(query)
    expanded = expand_query(corrected)
    actual = get_primary_category(expanded)
    assert actual == expected_cat, \
        f"{query!r} -> expected {expected_cat}, got {actual} (expanded: {expanded!r})"
