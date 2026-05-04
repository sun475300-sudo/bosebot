"""「보세전시장 운영에 관한 고시」 본문이 챗봇 답변에 반영되는지 확인.

전제 조건:
  - admRul 캐시(``data/law_sync.db`` 의 ``admrul_content_cache``)에 시드로
    등록된 admRulSeq=2100000276240 본문이 들어 있다 (테스트에서는 임시 DB).
  - 챗봇은 ``self.admrul_index`` 를 통해 본문을 조회할 수 있어야 한다.

테스트는 챗봇 인스턴스에 mock 한 admrul_index 를 주입한 뒤 골든 질의 5~10개에
대해 답변에 핵심 키워드가 포함되는지 확인한다. 외부 API 호출은 일어나지 않는다.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.chatbot import BondedExhibitionChatbot  # noqa: E402


# 시드 캐시에 들어갈 mock 조문 본문
MOCK_ARTICLES = {
    "제1조": "이 고시는 관세법 제190조에 따른 보세전시장의 운영에 관하여 필요한 사항을 정함을 목적으로 한다.",
    "제3조": "이 고시에서 사용하는 용어의 뜻은 운영인, 박람회 등으로 한다.",
    "제4조": "보세전시장의 특허장소는 박람회 등이 개최되는 회장 등으로 한다.",
    "제5조": "보세전시장의 특허기간은 해당 박람회 등의 회기 만료일까지로 한다.",
    "제6조": "운영인이 되려는 자는 특허신청서에 사업계획서 등을 첨부하여 세관장에게 제출한다.",
    "제10조": "운영인은 보세전시장에 외국물품을 반출입할 때에는 세관장에게 신고하여야 한다.",
    "제11조": "반입신고된 외국물품이 보세전시장에 반입된 경우 운영인은 세관공무원의 검사를 받아야 한다.",
    "제15조": "관세법 제178조 또는 제179조의 사유에 해당하는 경우 세관장은 특허를 취소하거나 보세전시장을 폐쇄할 수 있다.",
}

GOLDEN = [
    ("보세전시장 특허기간은 어떻게 되나요?",     ["특허기간", "회기"]),
    ("보세전시장 특허신청은 어떻게 하나요?",     ["신청", "특허"]),
    ("보세전시장의 특허장소는 어디인가요?",      ["특허장소", "박람회"]),
    ("보세전시장 반출입 신고는 어떻게 하나요?",   ["반출입", "신고"]),
    ("보세전시장 물품검사는 어떻게 진행되나요?", ["검사"]),
    ("보세전시장 운영인의 의무는 무엇인가요?",   ["운영인"]),
    ("보세전시장 폐쇄 사유는 무엇인가요?",        ["폐쇄", "취소"]),
    ("보세전시장 운영에 관한 고시의 목적은?",     ["고시", "보세전시장"]),
]


@pytest.fixture(scope="module")
def bot_with_admrul():
    bot = BondedExhibitionChatbot()
    # admrul_index 강제 주입 — 외부 API 의존성 제거
    by_law_basis = {
        f"보세전시장 운영에 관한 고시 {art}": body
        for art, body in MOCK_ARTICLES.items()
    }
    # FAQ 의 legal_basis 는 종종 "고시 제5조(특허기간)" 처럼 부제가 붙는다.
    # 부분 매칭이 동작하는지 확인하기 위해 일부러 추가 키도 등록한다.
    by_law_basis["보세전시장 운영에 관한 고시 제5조(특허기간)"] = MOCK_ARTICLES["제5조"]
    by_law_basis["보세전시장 운영에 관한 고시 제10조(반출입의 신고)"] = MOCK_ARTICLES["제10조"]
    by_law_basis["보세전시장 운영에 관한 고시 제11조(물품검사)"] = MOCK_ARTICLES["제11조"]

    bot.admrul_index = {
        "by_name": {
            "보세전시장 운영에 관한 고시": {
                "agency": "관세청",
                "effective_date": "20251101",
                "articles": dict(MOCK_ARTICLES),
                "admrul_seq": "2100000276240",
                "fetched_at": "2026-05-04T00:00:00",
            }
        },
        "by_law_basis": by_law_basis,
        "chunks": [
            {
                "id": f"admrul:2100000276240:{art}:0",
                "law_name": "보세전시장 운영에 관한 고시",
                "agency": "관세청",
                "article": art,
                "text": body,
                "admrul_seq": "2100000276240",
            }
            for art, body in MOCK_ARTICLES.items()
        ],
    }
    return bot


@pytest.mark.parametrize("query,expected_kws", GOLDEN)
def test_bonded_notice_question_returns_relevant_answer(
        bot_with_admrul, query, expected_kws):
    out = bot_with_admrul.process_query(query, include_metadata=True)
    response = out["response"] if isinstance(out, dict) else out
    assert response, f"empty answer for {query!r}"
    assert len(response) >= 30, (
        f"answer too short ({len(response)}): {response!r}"
    )
    assert any(kw in response for kw in expected_kws), (
        f"none of {expected_kws} found in answer: {response!r}"
    )


def test_admrul_lookup_exact_match(bot_with_admrul):
    body = bot_with_admrul._admrul_lookup_for_basis(
        "보세전시장 운영에 관한 고시 제5조"
    )
    assert body and "회기 만료일까지" in body


def test_admrul_lookup_with_subtitle(bot_with_admrul):
    """`제10조(반출입의 신고)` 처럼 부제가 붙은 basis 도 매칭되어야 한다."""
    body = bot_with_admrul._admrul_lookup_for_basis(
        "보세전시장 운영에 관한 고시 제10조(반출입의 신고)"
    )
    assert body and "반출입" in body


def test_admrul_lookup_unknown_returns_none(bot_with_admrul):
    assert bot_with_admrul._admrul_lookup_for_basis("관세법 제999조") is None
    assert bot_with_admrul._admrul_lookup_for_basis("") is None
    assert bot_with_admrul._admrul_lookup_for_basis(None) is None
