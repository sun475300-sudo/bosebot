"""Live-test 분류기 회귀 테스트.

reports/live_chatbot_test_20260504_094643.md 에서 발견된 3개 버그가
재발하지 않도록 강력하게 검증한다:

  Q1: "보세전시장에서 특허 기간이 얼마인가요?"
    - intent ∈ {patent_duration, patent_period}
    - category == PATENT
    - 답변에 "10년" 또는 "갱신" 또는 "특허 기간" 포함

  Q7: "보세전시장 물품 검사 어떻게 진행되나요?"
    - category ∈ {INSPECTION, GOODS_INSPECTION}
    - category != FOOD_TASTING
    - 답변에 "무작위" 또는 "정기 검사" 포함

  Q9: "특허 침해품 어떻게 처리하나요?"
    - intent.lower() 또는 category.lower() 에 "infringement" 포함
      또는 답변에 "침해" 포함

추가:
  - FOOD_TASTING 회귀: "시식용 식품 잔량 어떻게 처리하나요?" 가 여전히
    FOOD_TASTING 으로 분류되는지 (가드가 정상 동작) 확인.
"""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from src.chatbot import BondedExhibitionChatbot
from src.classifier import classify_query, classify_intent, fast_path_category


# ---------------------------------------------------------------------------
# 단위 테스트: classifier API 직접 호출
# ---------------------------------------------------------------------------

class TestFastPathClassifier:
    """fast_path_category / classify_intent 직접 검증."""

    def test_q1_patent_duration_intent(self):
        intent_id, conf = classify_intent("보세전시장에서 특허 기간이 얼마인가요?")
        assert intent_id in {"patent_duration", "patent_period"}, (
            f"expected patent_duration intent, got {intent_id}"
        )
        assert conf >= 0.8, f"fast-path 신뢰도가 낮음: {conf}"

    def test_q1_patent_category(self):
        cats = classify_query("보세전시장에서 특허 기간이 얼마인가요?")
        assert "PATENT" in cats
        assert cats[0] == "PATENT"

    def test_q1_fast_path_returns_patent(self):
        assert fast_path_category("보세전시장에서 특허 기간이 얼마인가요?") == "PATENT"

    def test_q7_goods_inspection_intent(self):
        intent_id, conf = classify_intent("보세전시장 물품 검사 어떻게 진행되나요?")
        assert intent_id in {"goods_inspection", "inspection"}, (
            f"expected goods_inspection intent, got {intent_id}"
        )
        assert conf >= 0.8

    def test_q7_inspection_category(self):
        cats = classify_query("보세전시장 물품 검사 어떻게 진행되나요?")
        assert cats[0] in {"INSPECTION", "GOODS_INSPECTION"}, (
            f"expected INSPECTION-like category, got {cats}"
        )
        assert "FOOD_TASTING" not in cats, (
            "FOOD_TASTING 으로 잘못 매칭됨 — Q7 회귀"
        )

    def test_q9_patent_infringement_intent(self):
        intent_id, conf = classify_intent("특허 침해품 어떻게 처리하나요?")
        assert "infringement" in intent_id.lower() or "침해" in intent_id, (
            f"expected infringement-related intent, got {intent_id}"
        )
        assert conf >= 0.8

    def test_q9_patent_infringement_category(self):
        cats = classify_query("특허 침해품 어떻게 처리하나요?")
        assert cats[0] == "PATENT_INFRINGEMENT"


# ---------------------------------------------------------------------------
# FOOD_TASTING 가드 회귀 — "시식용" 컨텍스트가 있을 때만 매치되어야 함
# ---------------------------------------------------------------------------

class TestFoodTastingGuard:
    def test_food_tasting_still_works_with_시식(self):
        cats = classify_query("시식용 식품 잔량 어떻게 처리하나요?")
        assert "FOOD_TASTING" in cats

    def test_food_tasting_NOT_triggered_by_검사_only(self):
        """단순 '검사' 키워드만으로는 FOOD_TASTING이 트리거되면 안된다."""
        cats = classify_query("물품 검사 어떻게 진행되나요?")
        assert "FOOD_TASTING" not in cats

    def test_food_tasting_NOT_triggered_by_식품_no_시식(self):
        """'식품' 키워드만으로는 FOOD_TASTING이 단독 트리거되면 안된다.

        (단, FOOD_TASTING_GUARD_TOKENS에 '식품'이 포함되어 있으므로 이 케이스는
        가드를 통과한다. 다만 INSPECTION이나 더 구체적인 카테고리가 있으면
        그쪽이 우선되어야 한다.)
        """
        # 동일 질의에서 INSPECTION 키워드가 있으면 INSPECTION 우선
        cats = classify_query("식품 물품 검사 절차")
        assert cats[0] == "INSPECTION"


# ---------------------------------------------------------------------------
# 통합 테스트: 챗봇 파이프라인 end-to-end
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bot():
    os.environ.setdefault("SKIP_HEAVY_DEPS", "1")
    return BondedExhibitionChatbot()


class TestEndToEndChatbot:
    """3개 버그 모두 챗봇 파이프라인에서 회귀하지 않도록 검증."""

    def test_q1_full_pipeline(self, bot):
        r = bot.process_query(
            "보세전시장에서 특허 기간이 얼마인가요?", include_metadata=True
        )
        assert r["intent_id"] in {"patent_duration", "patent_period"}, r["intent_id"]
        assert r["category"] == "PATENT", r["category"]
        ans = r["response"]
        assert "특허" in ans and ("10년" in ans or "갱신" in ans or "기간" in ans)

    def test_q7_full_pipeline(self, bot):
        r = bot.process_query(
            "보세전시장 물품 검사 어떻게 진행되나요?", include_metadata=True
        )
        assert r["category"] in {"INSPECTION", "GOODS_INSPECTION"}, r["category"]
        assert r["category"] != "FOOD_TASTING"
        ans = r["response"]
        assert ("무작위" in ans) or ("정기" in ans), (
            "물품 검사 답변에 무작위/정기 검사 키워드가 없음"
        )

    def test_q9_full_pipeline(self, bot):
        r = bot.process_query(
            "특허 침해품 어떻게 처리하나요?", include_metadata=True
        )
        intent_lower = (r["intent_id"] or "").lower()
        cat_lower = (r["category"] or "").lower()
        ans = r["response"]
        assert (
            "infringement" in intent_lower
            or "infringement" in cat_lower
            or "침해" in ans
        ), (
            f"intent={r['intent_id']}, category={r['category']}, "
            f"answer 첫 80자={ans[:80]!r}"
        )
