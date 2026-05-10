"""앙상블 FAQ 매처 정확도 테스트.

Golden testset (100개)으로 top-1, top-3 정확도를 측정한다.
CI 게이트: top-1 >= 0.70, top-3 >= 0.85
"""

import asyncio
import json
import sys
import pytest

sys.path.insert(0, ".")


def load_golden():
    with open("data/golden_testset.json", encoding="utf-8") as f:
        d = json.load(f)
    return d["items"]


def load_faq():
    with open("data/faq.json", encoding="utf-8") as f:
        d = json.load(f)
    return d["items"]


@pytest.fixture(scope="module")
def retriever():
    from app.services.matching.retriever import FAQRetriever
    from app.services.nlp.preprocessor import Preprocessor
    faq_items = load_faq()
    return FAQRetriever(faq_items), Preprocessor()


@pytest.mark.asyncio
async def test_ensemble_top1_accuracy(retriever):
    """앙상블 매처 top-1 정확도 >= 0.70."""
    ret, prep = retriever
    golden = load_golden()
    correct = 0
    for item in golden:
        pq = await prep.process(item["question"])
        hits, _ = await ret.retrieve(pq, top_k=1)
        if hits and hits[0].faq_id == item["expected_faq_id"]:
            correct += 1
    accuracy = correct / len(golden)
    print(f"\nTop-1 accuracy: {correct}/{len(golden)} = {accuracy:.2%}")
    assert accuracy >= 0.70, f"Top-1 정확도 {accuracy:.2%} < 70% (기준)"


@pytest.mark.asyncio
async def test_ensemble_top3_accuracy(retriever):
    """앙상블 매처 top-3 정확도 >= 0.85."""
    ret, prep = retriever
    golden = load_golden()
    correct = 0
    for item in golden:
        pq = await prep.process(item["question"])
        hits, _ = await ret.retrieve(pq, top_k=3)
        hit_ids = {h.faq_id for h in hits}
        if item["expected_faq_id"] in hit_ids:
            correct += 1
    accuracy = correct / len(golden)
    print(f"\nTop-3 accuracy: {correct}/{len(golden)} = {accuracy:.2%}")
    assert accuracy >= 0.85, f"Top-3 정확도 {accuracy:.2%} < 85% (기준)"


@pytest.mark.asyncio
async def test_match_explanation_populated(retriever):
    """MatchExplanation이 올바르게 채워지는지 확인한다."""
    ret, prep = retriever
    pq = await prep.process("보세전시장이 무엇인가요?")
    hits, explain = await ret.retrieve(pq, top_k=1)
    assert hits, "매칭 결과가 없음"
    assert explain.final_score >= 0.0
    assert explain.confidence_band in ("high", "medium", "low")
    assert explain.chosen_via in ("exact_alias", "ensemble", "llm_fallback")
