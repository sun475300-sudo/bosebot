"""Tests for Track RR — FAQ embedding warm-up."""
import json
import pytest
from src.embedding_warmup import pick_hot_faqs, warmup


@pytest.fixture
def faq_path(tmp_path):
    p = tmp_path / "faq.json"
    p.write_text(json.dumps([
        {"id":"A","question":"전시 신청 방법?"},
        {"id":"B","question":"비용은 얼마?"},
        {"id":"C","question":"신청 마감은?"},
        {"id":"D","question":"취소 가능?"},
    ], ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_pick_uses_usage_then_order(faq_path):
    with open(faq_path, encoding="utf-8") as f:
        faqs = json.load(f)
    out = pick_hot_faqs(faqs, {"C": 50, "A": 5}, top_n=3)
    assert out[0] == "신청 마감은?"
    assert out[1] == "전시 신청 방법?"


def test_warmup_calls_encoder(faq_path):
    calls = []
    res = warmup(encode_fn=lambda t: calls.append(t), faq_path=faq_path, top_n=2, enabled=True)
    assert res["ran"] and res["encoded"] == 2 and len(calls) == 2


def test_warmup_disabled_noop():
    calls = []
    res = warmup(encode_fn=lambda t: calls.append(t), enabled=False)
    assert not res["ran"] and res["reason"] == "disabled" and calls == []


def test_warmup_missing_faq(tmp_path):
    res = warmup(encode_fn=lambda t: None, faq_path=str(tmp_path / "x.json"), top_n=5, enabled=True)
    assert not res["ran"] and res["reason"] == "no_faqs"


def test_warmup_counts_errors(faq_path):
    res = warmup(encode_fn=lambda t: (_ for _ in ()).throw(RuntimeError("x")), faq_path=faq_path, top_n=2, enabled=True)
    assert res["ran"] and res["encoded"] == 0 and res["errors"] == 2
