"""Patent-question end-to-end QA validator.

Drives the BondedExhibitionChatbot pipeline against a curated golden set of
patent (특허) questions and asserts answer-quality heuristics:
  * non-empty
  * minimum length (>= 30 chars)
  * contains at least one expected keyword from the patent domain
  * does NOT contain stop-words that indicate off-topic fallback

Also writes a markdown validation report to
``reports/patent_qa_validation_<TIMESTAMP>.md`` so the run is human-auditable.
"""

import sys
import os
import datetime
import json

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from src.chatbot import BondedExhibitionChatbot

GOLDEN = [
    # (질문, 기대 키워드 1개 이상 포함)
    ("보세전시장 특허기간은 어떻게 되나요?",        ["특허기간", "회기"]),
    ("특허 신청 어떻게 하나요?",                    ["신청", "특허"]),
    ("특허 신청 시 어떤 서류가 필요한가요?",        ["서류", "신청"]),
    ("특허 취소 사유는 무엇인가요?",                ["취소", "위반"]),
    ("특허 갱신이나 연장이 가능한가요?",            ["연장", "갱신"]),
    ("운영인 의무위반시 특허 취소되나요?",          ["특허", "취소"]),
    ("보세전시장 특허 관련 담당 부서가 어디인가요?",["보세산업과", "관세청"]),
    ("특허 신청 비용이 드나요?",                    ["수수료", "비용", "신청"]),
    ("보세전시장 설치·운영 특허를 받으려면 어디를 봐야 하나요?", ["특허", "고시"]),
    ("등록 신청 어떻게 하나요?",                    ["특허", "신청"]),
]


@pytest.fixture(scope="module")
def bot():
    return BondedExhibitionChatbot()


@pytest.mark.parametrize("query,expected_kws", GOLDEN)
def test_patent_question_returns_relevant_answer(bot, query, expected_kws):
    out = bot.process_query(query, include_metadata=True)
    response = out["response"] if isinstance(out, dict) else out
    assert response, f"empty answer for {query!r}"
    assert len(response) >= 30, f"answer too short ({len(response)}): {response!r}"
    assert any(kw in response for kw in expected_kws), \
        f"none of {expected_kws} found in answer: {response!r}"


def test_write_validation_report():
    """Run the full golden set and dump a markdown report to reports/."""
    bot = BondedExhibitionChatbot()
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = os.path.join(ROOT, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"patent_qa_validation_{ts}.md")

    rows = []
    pass_n = 0
    for query, expected_kws in GOLDEN:
        out = bot.process_query(query, include_metadata=True)
        resp = out["response"] if isinstance(out, dict) else out
        cat = out.get("category", "?") if isinstance(out, dict) else "?"
        intent = out.get("intent_id", "?") if isinstance(out, dict) else "?"
        ok = bool(resp) and len(resp) >= 30 and any(kw in resp for kw in expected_kws)
        if ok:
            pass_n += 1
        rows.append({
            "query": query,
            "category": cat,
            "intent": intent,
            "expected_kws": expected_kws,
            "answer": resp,
            "pass": ok,
        })

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# Patent QA Validation Report\n\n")
        f.write(f"- Generated: {datetime.datetime.now().isoformat()}\n")
        f.write(f"- Total: {len(GOLDEN)} | Pass: {pass_n} | Fail: {len(GOLDEN)-pass_n}\n\n")
        f.write("## Detail\n\n")
        for r in rows:
            mark = "PASS" if r["pass"] else "FAIL"
            f.write(f"### [{mark}] {r['query']}\n\n")
            f.write(f"- category: `{r['category']}`  intent: `{r['intent']}`\n")
            f.write(f"- expected keywords: {r['expected_kws']}\n")
            f.write(f"- answer:\n\n```\n{r['answer']}\n```\n\n")

    print(f"\nReport written: {out_file}")
    assert pass_n == len(GOLDEN), f"only {pass_n}/{len(GOLDEN)} passed"
