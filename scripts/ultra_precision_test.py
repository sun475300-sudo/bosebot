"""초정밀 테스트 — held-out + 적대적 + 오타 + FAQ 답변 품질 점검.

PART A: 골든셋 회귀 (100)
PART B: Held-out 신규문구 — 처음 작성 시점에 variants에 없는 문구.
        실패 케이스를 차후 variants에 추가하면 다음 회차부터는 회귀가드 역할로 전환됨.
        (test_state: variants 포함 여부는 실행 시 자동 감지하여 보고)
PART C: 적대적 교차 FAQ — 어휘 중첩 케이스 (~30)
PART D: 오타/띄어쓰기 변형 (~30)
PART E: FAQ 답변 품질 감사 (legal_basis/keywords/길이/한글 검증)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.matching.retriever import FAQRetriever  # noqa: E402
from app.services.nlp.preprocessor import Preprocessor  # noqa: E402


# ====================================================================
# PART B: Held-out 신규문구 — variants.json에 없는 문구만
# ====================================================================
HELDOUT: list[dict] = [
    # GENERAL
    {"q": "보세전시장이라는 곳이 정확히 어떤 시설입니까", "exp": "A", "cat": "GENERAL"},
    {"q": "해외 박람회용 외국물품 보관 전시 시설을 뭐라고 부르나요", "exp": "A", "cat": "GENERAL"},
    {"q": "보세전시장과 일반 보세창고의 결정적 차이가 뭐예요", "exp": "T", "cat": "GENERAL"},
    {"q": "외국기업도 보세전시장을 신청해서 쓸 수 있나요", "exp": "U", "cat": "GENERAL"},
    {"q": "국내제조 물품을 보세전시장 안에 전시해도 문제없나요", "exp": "AC", "cat": "GENERAL"},
    {"q": "박람회 주관사로서 보세전시장에서 행사 진행하려면 미리 챙길 것은", "exp": "AJ", "cat": "GENERAL"},
    {"q": "이 고시 자체가 만들어진 취지가 뭔지 궁금합니다", "exp": "BC", "cat": "GENERAL"},
    {"q": "보세전시장 운영주체로 등록되려면 어떤 자격을 갖춰야 하죠", "exp": "AR", "cat": "GENERAL"},

    # IMPORT_EXPORT
    {"q": "전시품 들여올 때 매번 세관에 알려야 하나요", "exp": "B", "cat": "IMPORT_EXPORT"},
    {"q": "끝나고 외국으로 돌려보낼 때 거쳐야 하는 절차는요", "exp": "V", "cat": "IMPORT_EXPORT"},
    {"q": "전시 후에 남은 외국물품을 그대로 둘 수는 없잖아요 어떻게 정리하나요", "exp": "W", "cat": "IMPORT_EXPORT"},
    {"q": "들여온 물품에 대해 세관 직원이 확인하는 과정이 따로 있나요", "exp": "AB", "cat": "IMPORT_EXPORT"},
    {"q": "전시품 단가나 가격을 신고할 때 어떤 방식으로 하나요", "exp": "AL", "cat": "IMPORT_EXPORT"},
    {"q": "동일 회사가 운영하는 두 보세전시장 사이에서 짐을 옮길 수 있는지", "exp": "AS", "cat": "IMPORT_EXPORT"},

    # SALES
    {"q": "관람객한테 그 자리에서 전시품을 팔아도 합법인가요", "exp": "C", "cat": "SALES"},
    {"q": "오늘 계약서만 쓰고 인도는 나중에 통관 후 하면 되나요", "exp": "X", "cat": "SALES"},
    {"q": "현장 판매 후 수금은 어떤 방식으로 처리해요", "exp": "AD", "cat": "SALES"},
    {"q": "판매할 물품마다 따로 수입면허 절차를 밟아야 하나요", "exp": "AE", "cat": "SALES"},

    # SAMPLE
    {"q": "전시품을 견본 명목으로 외부에 잠깐 가지고 나갈 수 있는지", "exp": "D", "cat": "SAMPLE"},
    {"q": "견본품으로 빠진 물품에는 관세 부과 되는 거 맞죠", "exp": "Z", "cat": "SAMPLE"},
    {"q": "견본 반출 허가 받는 절차는 어디서 진행하나요", "exp": "M", "cat": "SAMPLE"},
    {"q": "한 번에 견본으로 가져갈 수 있는 개수에 상한이 있나요", "exp": "AF", "cat": "SAMPLE"},
    {"q": "외부로 가지고 나간 견본은 일정 기간 후 다시 가져와야 하나요", "exp": "AG", "cat": "SAMPLE"},

    # FOOD_TASTING
    {"q": "시식용 식품도 일반 수입신고처럼 요건확인을 받아야 하는지", "exp": "E", "cat": "FOOD_TASTING"},
    {"q": "시식하고 남은 음식을 폐기하는 정해진 방식이 있나요", "exp": "Y", "cat": "FOOD_TASTING"},
    {"q": "시식 행사용 식품 반입에 양적 제약은 있는 편인가요", "exp": "AH", "cat": "FOOD_TASTING"},
    {"q": "시식 코너 운영 전에 세관에 미리 알려야 하나요", "exp": "AI", "cat": "FOOD_TASTING"},
    {"q": "외국 시식 식품에 우리말 표기 라벨 의무가 있나요", "exp": "AV", "cat": "FOOD_TASTING"},

    # LICENSE
    {"q": "한 번 받은 보세전시장 특허는 몇 년간 유효한가요", "exp": "F", "cat": "LICENSE"},
    {"q": "특허를 새로 받으려면 어떤 법 조항을 살펴야 하나요", "exp": "G", "cat": "LICENSE"},
    {"q": "기간이 끝나기 전에 미리 연장 신청 가능한가요", "exp": "AA", "cat": "LICENSE"},
    {"q": "특허가 박탈되는 케이스에는 어떤 게 있죠", "exp": "AK", "cat": "LICENSE"},
    {"q": "특허 신청할 때 별도 비용이 발생하나요", "exp": "AT", "cat": "LICENSE"},

    # EXHIBITION
    {"q": "전시할 수 없도록 제외되는 품목이 정해져 있나요", "exp": "H", "cat": "EXHIBITION"},
    {"q": "전시장 안에 놓인 외국물품을 다른 용도로 활용해도 되는지", "exp": "I", "cat": "EXHIBITION"},
    {"q": "방문객 앞에서 제품 시연하는 것도 가능한가요", "exp": "J", "cat": "EXHIBITION"},
    {"q": "기간 도중 다른 신규 모델로 바꿔서 전시해도 되는지", "exp": "AM", "cat": "EXHIBITION"},
    {"q": "전시장 안에서 물품 안전하게 보관할 때 신경 쓸 점은", "exp": "AN", "cat": "EXHIBITION"},
    {"q": "전시 부스 안에서 사진이나 영상 촬영해도 무방한가요", "exp": "AU", "cat": "EXHIBITION"},

    # DOCUMENTS
    {"q": "반출입신고서라는 서류는 어떤 양식인가요", "exp": "K", "cat": "DOCUMENTS"},
    {"q": "특허 신청 서류로 무엇 무엇이 필요한지 알려주세요", "exp": "L", "cat": "DOCUMENTS"},
    {"q": "수입면허 받을 때 첨부해야 할 서류 종류가 어떻게 되나요", "exp": "AO", "cat": "DOCUMENTS"},
    {"q": "보세전시장 사업 종료할 때 제출하는 보고서가 있나요", "exp": "AW", "cat": "DOCUMENTS"},

    # PENALTIES
    {"q": "정식 허가 없이 물품을 외부로 빼낸 경우 어떤 처벌을 받나요", "exp": "N", "cat": "PENALTIES"},
    {"q": "수입면허도 없이 판매목적으로 사용했다가 적발되면 어떻게 되나요", "exp": "O", "cat": "PENALTIES"},
    {"q": "운영인의 법적 의무 위반시 받는 행정처분은 어떤 게 있죠", "exp": "P", "cat": "PENALTIES"},
    {"q": "과태료는 금액이 어떻게 정해지나요", "exp": "AP", "cat": "PENALTIES"},
    {"q": "의무 어긴 운영인의 특허가 박탈될 수도 있나요", "exp": "BA", "cat": "PENALTIES"},
    {"q": "어떤 사유가 있으면 보세전시장이 강제로 닫히게 되나요", "exp": "BB", "cat": "PENALTIES"},

    # CONTACT
    {"q": "보세전시장 일반 안내 받으려면 어디 연락처로 하나요", "exp": "Q", "cat": "CONTACT"},
    {"q": "UNI-PASS 접속이 안되는데 신고 창구가 어디예요", "exp": "R", "cat": "CONTACT"},
    {"q": "특허 관련 업무 담당하는 부서는 어디인지 알려주세요", "exp": "S", "cat": "CONTACT"},
    {"q": "관세 처분에 불복하고 싶을 때 밟아야 할 절차는요", "exp": "AQ", "cat": "CONTACT"},
    {"q": "관세사를 통해서 신청 업무 위임할 수 있나요", "exp": "AX", "cat": "CONTACT"},

    # INSPECTION / PATENT_INFRINGEMENT
    {"q": "반입된 외국물품 검사는 어떤 흐름으로 진행되나요", "exp": "AY", "cat": "INSPECTION"},
    {"q": "전시 중에 위조품으로 보이는 물건을 발견하면 어떻게 신고하나요", "exp": "AZ", "cat": "PATENT_INFRINGEMENT"},
]

# ====================================================================
# PART C: 적대적 교차 FAQ — 어휘 중첩, 의도는 명확
# ====================================================================
ADVERSARIAL: list[dict] = [
    # "운영인" 중첩: P (의무위반 처분) vs BA (특허취소) vs AR (자격요건) vs AW (운영종료보고)
    {"q": "운영인 의무 안 지키면 어떻게 되나요", "exp": "P", "note": "P vs BA"},
    {"q": "운영인이 의무 어겨서 특허가 취소될 수 있는지", "exp": "BA", "note": "BA vs P"},
    {"q": "운영인이 갖춰야할 자격이 어떻게 되나요", "exp": "AR", "note": "AR vs P"},
    {"q": "보세전시장 운영 끝나면 보고하는 서류 뭐 있어요", "exp": "AW", "note": "AW vs L vs K"},

    # "특허" 중첩: F(기간) vs G(신청근거) vs AA(갱신) vs AK(취소) vs AT(수수료) vs L(서류)
    {"q": "특허 기간 알려주세요", "exp": "F", "note": "F vs AA"},
    {"q": "특허 만료 전에 연장하는 방법", "exp": "AA", "note": "AA vs F"},
    {"q": "특허 받는 데 드는 비용", "exp": "AT", "note": "AT vs G"},
    {"q": "특허 신청 근거 법령 알려줘", "exp": "G", "note": "G vs AT vs L"},
    {"q": "특허 신청 시 필요 서류 목록", "exp": "L", "note": "L vs G"},
    {"q": "특허가 취소되는 사유", "exp": "AK", "note": "AK vs BA"},

    # "견본품" 중첩: D(반출) vs Z(관세) vs M(허가) vs AF(수량) vs AG(반환)
    {"q": "견본품 외부 반출이 가능한가요", "exp": "D", "note": "D vs M"},
    {"q": "견본품 반출 허가 신청은 어디에", "exp": "M", "note": "M vs D"},
    {"q": "견본품에 부과되는 세금", "exp": "Z", "note": "Z vs AF"},
    {"q": "견본품 수량 상한선 있나요", "exp": "AF", "note": "AF vs Z"},
    {"q": "견본품 외부로 빼낸 후 반납 의무 있어요", "exp": "AG", "note": "AG vs D"},

    # "시식" 중첩: E(요건확인) vs Y(사후처리) vs AH(수량) vs AI(사전신고) vs AV(라벨)
    {"q": "시식 식품 요건확인 면제 받을 수 있나요", "exp": "E", "note": "E vs AI"},
    {"q": "시식 식품 라벨 한글로 붙여야 하나요", "exp": "AV", "note": "AV vs AH"},
    {"q": "시식 행사 시작 전에 신고하는 거 맞죠", "exp": "AI", "note": "AI vs E"},
    {"q": "시식 끝나고 남은 식품 처리 방법", "exp": "Y", "note": "Y vs AH"},
    {"q": "시식용으로 들여올 수 있는 식품 수량 한도", "exp": "AH", "note": "AH vs AF"},

    # "반출입" 중첩: B(의무) vs K(신고서) vs N(무허가 처벌) vs AS(전시장 간)
    {"q": "반출입 시 신고서 양식은 어떤거", "exp": "K", "note": "K vs B"},
    {"q": "허가 없이 반출했을 때 처벌은", "exp": "N", "note": "N vs B"},
    {"q": "물품 반입할때 의무적으로 신고해야 하나요", "exp": "B", "note": "B vs K"},
    {"q": "보세전시장 사이에서 물품 옮기는 거 가능", "exp": "AS", "note": "AS vs B"},

    # "판매" 중첩: C(현장) vs X(계약후통관) vs AD(정산) vs AE(수입면허) vs O(무면허처벌)
    {"q": "전시한 물품 현장에서 바로 판매 OK?", "exp": "C", "note": "C vs X"},
    {"q": "수입면허 없이 판매하다 걸리면", "exp": "O", "note": "O vs AE"},
    {"q": "판매 전에 받는 수입면허 절차", "exp": "AE", "note": "AE vs O"},
    {"q": "판매 대금 정산은 어떻게 하나요", "exp": "AD", "note": "AD vs C"},
    {"q": "계약만 하고 통관은 추후에 가능한가", "exp": "X", "note": "X vs C"},
]

# ====================================================================
# PART D: 오타/띄어쓰기 변형
# ====================================================================
TYPO: list[dict] = [
    # 띄어쓰기
    {"q": "보세 전시장 이무엇인가요", "exp": "A"},
    {"q": "보세전시장이뭐예요", "exp": "A"},
    {"q": "보세 전시장 특허 기간", "exp": "F"},
    {"q": "운영인자격요건", "exp": "AR"},
    {"q": "견본품 반출 허가 신청", "exp": "M"},
    {"q": "시식식품 요건확인", "exp": "E"},
    {"q": "관세사대행", "exp": "AX"},
    # 자모 오타
    {"q": "보세전시장이 무엇인가용", "exp": "A"},
    {"q": "운영인 요건 알려줘여", "exp": "AR"},
    {"q": "특허 갱신 가능항요", "exp": "AA"},
    {"q": "위조품 발견 시 처리법", "exp": "AZ"},
    # 받침 오류
    {"q": "보세전시장 운영하라면 자격이 필요한가요", "exp": "AR"},
    {"q": "전시품 외부 반춥 가능여부", "exp": "D"},
    {"q": "시식 행사 사전 신고 의문", "exp": "AI"},
    # 영어 약어 혼용
    {"q": "Bonded exhibition area 운영인 자격", "exp": "AR"},
    {"q": "UNI PASS 오류 신고 어디", "exp": "R"},
    {"q": "보세전시장 license 기간", "exp": "F"},
    # 부호 변형
    {"q": "보세전시장이란? 정의는?", "exp": "A"},
    {"q": "특허취소-사유", "exp": "AK"},
    {"q": "견본품/관세 부과 여부", "exp": "Z"},
    # 동음이의/유사
    {"q": "특허취소사유알려줘", "exp": "AK"},
    {"q": "전시장에서판매할수있나요", "exp": "C"},
    {"q": "운영인의무위반시처분", "exp": "P"},
    # 줄임/요약
    {"q": "보세전시장이란", "exp": "A"},
    {"q": "운영인 요건", "exp": "AR"},
    {"q": "견본품 관세", "exp": "Z"},
    {"q": "시식 식품 요건", "exp": "E"},
    {"q": "특허 기간", "exp": "F"},
    {"q": "관세사 대행 가능", "exp": "AX"},
    {"q": "물품 반출 허가 없으면", "exp": "N"},
    {"q": "보세전시장 폐쇄", "exp": "BB"},
]


async def run_query(ret, prep, q):
    t0 = time.perf_counter()
    pq = await prep.process(q)
    hits, ex = await ret.retrieve(pq, top_k=3)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return hits, ex, elapsed_ms


def audit_faq_quality(faq_items):
    """FAQ 답변 품질 감사."""
    findings = {
        "missing_legal_basis": [],
        "missing_keywords": [],
        "short_answer": [],
        "empty_answer": [],
        "missing_category": [],
        "duplicate_questions": [],
    }
    seen_q = {}
    for it in faq_items:
        fid = it.get("id", "")
        ans = it.get("answer", "")
        q = it.get("question", "").strip()
        if not it.get("legal_basis"):
            findings["missing_legal_basis"].append((fid, it.get("category", ""), q[:50]))
        if not it.get("keywords"):
            findings["missing_keywords"].append((fid, it.get("category", ""), q[:50]))
        if not ans:
            findings["empty_answer"].append((fid, q[:50]))
        elif len(ans) < 80:
            findings["short_answer"].append((fid, len(ans), ans[:80]))
        if not it.get("category"):
            findings["missing_category"].append((fid, q[:50]))
        if q in seen_q:
            findings["duplicate_questions"].append((seen_q[q], fid, q[:50]))
        else:
            seen_q[q] = fid
    return findings


def hangul_ratio(s: str) -> float:
    if not s:
        return 0.0
    han = sum(1 for c in s if "가" <= c <= "힣")
    return han / len(s)


async def main():
    with open("data/faq.json", encoding="utf-8") as f:
        faq_items = json.load(f)["items"]
    with open("data/golden_testset.json", encoding="utf-8") as f:
        golden = json.load(f)["items"]
    with open("data/question_variants.json", encoding="utf-8") as f:
        variants_data = json.load(f)

    # 변형 중복 검출 — held-out queries가 variants에 들어가있지 않은지 확인
    variant_strings = set()
    for e in variants_data.get("variants", []):
        variant_strings.add(e.get("original_question", "").strip())
        for v in e.get("variants", []):
            variant_strings.add(v.strip())
    leaked = [t for t in HELDOUT if t["q"].strip() in variant_strings]
    leaked_pct = len(leaked) / len(HELDOUT) * 100 if HELDOUT else 0
    if leaked:
        print(f"PART B 상태: {len(leaked)}/{len(HELDOUT)} ({leaked_pct:.0f}%)가 variants에 등록됨 → 회귀가드 모드")
    else:
        print("PART B 상태: variants와 완전 분리 → 진짜 일반화 측정 모드")

    ret = FAQRetriever(faq_items)
    prep = Preprocessor()

    # PART A — 골든셋 회귀
    print()
    print("=" * 72)
    print(f"PART A: 골든셋 회귀 ({len(golden)}문항)")
    print("=" * 72)
    a_t1 = a_t3 = 0
    for item in golden:
        hits, _, _ = await run_query(ret, prep, item["question"])
        top1 = hits[0].faq_id if hits else None
        if top1 == item["expected_faq_id"]:
            a_t1 += 1
        if item["expected_faq_id"] in [h.faq_id for h in hits]:
            a_t3 += 1
    print(f"Top-1: {a_t1}/{len(golden)} = {a_t1/len(golden)*100:.1f}%")
    print(f"Top-3: {a_t3}/{len(golden)} = {a_t3/len(golden)*100:.1f}%")

    # PART B — Held-out
    print()
    print("=" * 72)
    print(f"PART B: Held-out 신규문구 ({len(HELDOUT)}문항) — variants에 없는 문구만")
    print("=" * 72)
    b_t1 = b_t3 = 0
    b_by_cat = defaultdict(lambda: [0, 0, 0])
    b_fails = []
    for i, t in enumerate(HELDOUT, 1):
        hits, ex, _ = await run_query(ret, prep, t["q"])
        top1 = hits[0].faq_id if hits else None
        top3 = [h.faq_id for h in hits]
        score = hits[0].score if hits else 0.0
        ok1 = top1 == t["exp"]
        ok3 = t["exp"] in top3
        b_t1 += int(ok1)
        b_t3 += int(ok3)
        b_by_cat[t["cat"]][0] += 1
        b_by_cat[t["cat"]][1] += int(ok1)
        b_by_cat[t["cat"]][2] += int(ok3)
        if not ok1:
            b_fails.append((i, t, top1, top3, score, ex.chosen_via, ex.confidence_band))
    print(f"Top-1: {b_t1}/{len(HELDOUT)} = {b_t1/len(HELDOUT)*100:.1f}%")
    print(f"Top-3: {b_t3}/{len(HELDOUT)} = {b_t3/len(HELDOUT)*100:.1f}%")
    print("\n[카테고리별]")
    for k, (tot, t1, t3) in sorted(b_by_cat.items()):
        print(f"  {k:<22} {t1:>2}/{tot:<2} top-1={t1/tot*100:5.1f}%  top-3={t3/tot*100:5.1f}%")
    if b_fails:
        print(f"\n[Top-1 실패 {len(b_fails)}건]")
        for i, t, top1, top3, score, via, band in b_fails:
            in3 = "(Top3 O)" if t["exp"] in top3 else "(Top3 X)"
            print(f"  #{i:3d} [{t['cat']}] exp={t['exp']} got={top1} top3={top3} {in3}")
            print(f"        via={via} band={band} score={score:.3f}  Q={t['q']}")

    # PART C — 적대적 교차
    print()
    print("=" * 72)
    print(f"PART C: 적대적 교차 FAQ ({len(ADVERSARIAL)}문항) — 어휘 중첩 케이스")
    print("=" * 72)
    c_t1 = c_t3 = 0
    c_fails = []
    for i, t in enumerate(ADVERSARIAL, 1):
        hits, ex, _ = await run_query(ret, prep, t["q"])
        top1 = hits[0].faq_id if hits else None
        top3 = [h.faq_id for h in hits]
        score = hits[0].score if hits else 0.0
        ok1 = top1 == t["exp"]
        ok3 = t["exp"] in top3
        c_t1 += int(ok1)
        c_t3 += int(ok3)
        if not ok1:
            c_fails.append((i, t, top1, top3, score, ex.chosen_via, ex.confidence_band))
    print(f"Top-1: {c_t1}/{len(ADVERSARIAL)} = {c_t1/len(ADVERSARIAL)*100:.1f}%")
    print(f"Top-3: {c_t3}/{len(ADVERSARIAL)} = {c_t3/len(ADVERSARIAL)*100:.1f}%")
    if c_fails:
        print(f"\n[Top-1 실패 {len(c_fails)}건]")
        for i, t, top1, top3, score, via, band in c_fails:
            in3 = "(Top3 O)" if t["exp"] in top3 else "(Top3 X)"
            print(f"  #{i:3d} exp={t['exp']} got={top1} top3={top3} {in3}  [{t.get('note','')}]")
            print(f"        via={via} band={band} score={score:.3f}  Q={t['q']}")

    # PART D — 오타/띄어쓰기
    print()
    print("=" * 72)
    print(f"PART D: 오타/띄어쓰기 변형 ({len(TYPO)}문항)")
    print("=" * 72)
    d_t1 = d_t3 = 0
    d_fails = []
    for i, t in enumerate(TYPO, 1):
        hits, ex, _ = await run_query(ret, prep, t["q"])
        top1 = hits[0].faq_id if hits else None
        top3 = [h.faq_id for h in hits]
        score = hits[0].score if hits else 0.0
        ok1 = top1 == t["exp"]
        ok3 = t["exp"] in top3
        d_t1 += int(ok1)
        d_t3 += int(ok3)
        if not ok1:
            d_fails.append((i, t, top1, top3, score, ex.chosen_via, ex.confidence_band))
    print(f"Top-1: {d_t1}/{len(TYPO)} = {d_t1/len(TYPO)*100:.1f}%")
    print(f"Top-3: {d_t3}/{len(TYPO)} = {d_t3/len(TYPO)*100:.1f}%")
    if d_fails:
        print(f"\n[Top-1 실패 {len(d_fails)}건]")
        for i, t, top1, top3, score, via, band in d_fails:
            in3 = "(Top3 O)" if t["exp"] in top3 else "(Top3 X)"
            print(f"  #{i:3d} exp={t['exp']} got={top1} top3={top3} {in3}")
            print(f"        via={via} band={band} score={score:.3f}  Q={t['q']}")

    # PART E — 답변 품질 감사
    print()
    print("=" * 72)
    print(f"PART E: FAQ 답변 품질 감사 ({len(faq_items)}개)")
    print("=" * 72)
    findings = audit_faq_quality(faq_items)
    print(f"빈 답변:           {len(findings['empty_answer'])}건")
    print(f"짧은 답변 (<80자): {len(findings['short_answer'])}건")
    print(f"legal_basis 누락:  {len(findings['missing_legal_basis'])}건")
    print(f"keywords 누락:     {len(findings['missing_keywords'])}건")
    print(f"category 누락:     {len(findings['missing_category'])}건")
    print(f"중복 질문:         {len(findings['duplicate_questions'])}건")

    if findings["missing_legal_basis"]:
        print("\n  [legal_basis 누락 항목]")
        for fid, cat, q in findings["missing_legal_basis"]:
            print(f"    {fid} [{cat}] {q}")
    if findings["short_answer"]:
        print("\n  [짧은 답변 항목]")
        for fid, ln, ans in findings["short_answer"]:
            print(f"    {fid} ({ln}자) {ans}")

    # 한글 비율 검증 (의심 답변)
    suspect_lang = []
    for it in faq_items:
        r = hangul_ratio(it.get("answer", ""))
        if r < 0.3:  # 한글 30% 미만이면 의심
            suspect_lang.append((it["id"], r, it["answer"][:60]))
    print(f"한글 30% 미만 답변: {len(suspect_lang)}건")
    for fid, r, ans in suspect_lang:
        print(f"    {fid} ({r:.0%}) {ans}")

    # 종합
    print()
    print("=" * 72)
    print("종합 요약")
    print("=" * 72)
    total_q = len(golden) + len(HELDOUT) + len(ADVERSARIAL) + len(TYPO)
    total_t1 = a_t1 + b_t1 + c_t1 + d_t1
    total_t3 = a_t3 + b_t3 + c_t3 + d_t3
    print(f"  전체 매칭 문항: {total_q}")
    print(f"  Top-1: {total_t1}/{total_q} = {total_t1/total_q*100:.1f}%")
    print(f"  Top-3: {total_t3}/{total_q} = {total_t3/total_q*100:.1f}%")
    print(f"  ├ A 골든셋:     {a_t1}/{len(golden)}  ({a_t1/len(golden)*100:.0f}%)")
    print(f"  ├ B Held-out:   {b_t1}/{len(HELDOUT)}  ({b_t1/len(HELDOUT)*100:.0f}%)")
    print(f"  ├ C 적대적:     {c_t1}/{len(ADVERSARIAL)}  ({c_t1/len(ADVERSARIAL)*100:.0f}%)")
    print(f"  └ D 오타:       {d_t1}/{len(TYPO)}  ({d_t1/len(TYPO)*100:.0f}%)")
    print()
    print(f"  답변 품질 이슈:  legal_basis 누락 {len(findings['missing_legal_basis'])}, 짧은 답변 {len(findings['short_answer'])}")


if __name__ == "__main__":
    asyncio.run(main())
