"""확장 정밀 테스트 — 100문항 골든셋 + 신규 80문항(패러프레이즈/엣지/오타/모호).

목표:
  1. 기존 100문항 골든셋 회귀 확인 (100% 유지)
  2. 신규 80문항 challenge set으로 강건성 측정
  3. 운영인 요건(AR) ↔ 시식식품(E) 오매칭 회귀 가드
  4. 결과를 reports/extended_precision_test.txt에 저장
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


# 신규 challenge set — 카테고리별 강건성 평가용
# 유형: paraphrase(P), abbreviation(AB), typo(TY), edge/ambiguous(EG), 운영인-guard(GR)
EXTENDED_TESTS: list[dict] = [
    # === 운영인 요건 회귀 가드 (AR) — 시식식품 E와 어휘적으로 가까운 케이스 포함 ===
    {"q": "운영인의 요건을 알려줘", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 요건이 어떻게 되나요?", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 자격조건을 알고싶어요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인이 되기 위한 자격은?", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영자 요건이 뭔가요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "보세전시장 운영인 자격 알려주세요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 자격조건 궁금합니다", "exp": "AR", "type": "GR", "cat": "GENERAL"},

    # === 일반 (GENERAL) ===
    {"q": "보세전시장이라는게 도대체 뭔지 설명해주세요", "exp": "A", "type": "P", "cat": "GENERAL"},
    {"q": "보세창고랑 보세전시장 비교 좀", "exp": "T", "type": "P", "cat": "GENERAL"},
    {"q": "내국물품 전시 가능여부", "exp": "AC", "type": "AB", "cat": "GENERAL"},
    {"q": "행사 주최 시 준비사항", "exp": "AJ", "type": "AB", "cat": "GENERAL"},
    {"q": "이 고시 목적이 뭐죠?", "exp": "BC", "type": "P", "cat": "GENERAL"},
    {"q": "보세전시장 이용 대상자는 누구인가요?", "exp": "U", "type": "P", "cat": "GENERAL"},

    # === 반출입 (IMPORT_EXPORT) ===
    {"q": "전시 끝난 물품 해외 재반송하려면?", "exp": "V", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "전시장 간 물품이동 가능여부 알려주세요", "exp": "AS", "type": "AB", "cat": "IMPORT_EXPORT"},
    {"q": "세관 검사 절차가 궁금해요 (보세전시장)", "exp": "AB", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "잔여물품 처리방법", "exp": "W", "type": "AB", "cat": "IMPORT_EXPORT"},
    {"q": "반입물품 가액신고 어떻게 하나요", "exp": "AL", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "물품 반입 반출 신고 의무가 있나요?", "exp": "B", "type": "P", "cat": "IMPORT_EXPORT"},

    # === 판매 (SALES) ===
    {"q": "전시장에서 즉시 판매 가능?", "exp": "C", "type": "P", "cat": "SALES"},
    {"q": "계약만 먼저 하고 통관은 나중에 가능?", "exp": "X", "type": "P", "cat": "SALES"},
    {"q": "수입면허 신청 절차 (판매전)", "exp": "AE", "type": "P", "cat": "SALES"},
    {"q": "판매대금 정산 방법", "exp": "AD", "type": "AB", "cat": "SALES"},

    # === 견본품 (SAMPLE) ===
    {"q": "샘플 외부반출 가능여부", "exp": "D", "type": "P", "cat": "SAMPLE"},
    {"q": "견본품 관세 부과되나요?", "exp": "Z", "type": "P", "cat": "SAMPLE"},
    {"q": "견본품 반출 후 다시 돌려놔야 하나요", "exp": "AG", "type": "P", "cat": "SAMPLE"},
    {"q": "샘플 반출 허가 신청처가 어디인가요", "exp": "M", "type": "P", "cat": "SAMPLE"},
    {"q": "견본품 수량 한도", "exp": "AF", "type": "AB", "cat": "SAMPLE"},

    # === 시식 (FOOD_TASTING) — 운영인 요건과 비슷한 어휘 충돌 가드 포함 ===
    {"q": "시식 식품 요건확인 면제되는지", "exp": "E", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식 식품 라벨 표기 의무", "exp": "AV", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식 식품 반입수량 제한 있어요?", "exp": "AH", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식행사 사전신고 의무?", "exp": "AI", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식 후 남은 식품 처리법", "exp": "Y", "type": "P", "cat": "FOOD_TASTING"},

    # === 특허/라이선스 (LICENSE) ===
    {"q": "특허기간 얼마나 되나요", "exp": "F", "type": "AB", "cat": "LICENSE"},
    {"q": "특허 갱신 가능?", "exp": "AA", "type": "P", "cat": "LICENSE"},
    {"q": "특허취소 사유는?", "exp": "AK", "type": "AB", "cat": "LICENSE"},
    {"q": "특허신청 수수료 있나요", "exp": "AT", "type": "P", "cat": "LICENSE"},
    {"q": "특허신청 근거 어디 봐야하나요", "exp": "G", "type": "P", "cat": "LICENSE"},

    # === 전시 (EXHIBITION) ===
    {"q": "전시품 종류 제한", "exp": "H", "type": "AB", "cat": "EXHIBITION"},
    {"q": "장치된 물품 사용범위", "exp": "I", "type": "AB", "cat": "EXHIBITION"},
    {"q": "데모 시연 가능?", "exp": "J", "type": "P", "cat": "EXHIBITION"},
    {"q": "전시 중 물품 교체 가능?", "exp": "AM", "type": "P", "cat": "EXHIBITION"},
    {"q": "전시장 보관 주의사항", "exp": "AN", "type": "AB", "cat": "EXHIBITION"},
    {"q": "전시장 사진촬영/홍보 활동 가능?", "exp": "AU", "type": "P", "cat": "EXHIBITION"},

    # === 서류 (DOCUMENTS) ===
    {"q": "반출입신고서 양식이 뭔가요", "exp": "K", "type": "P", "cat": "DOCUMENTS"},
    {"q": "특허신청 시 제출서류 목록", "exp": "L", "type": "P", "cat": "DOCUMENTS"},
    {"q": "수입면허 신청서류", "exp": "AO", "type": "AB", "cat": "DOCUMENTS"},
    {"q": "운영 종료 보고서 제출 방법", "exp": "AW", "type": "P", "cat": "DOCUMENTS"},

    # === 제재 (PENALTIES) ===
    {"q": "허가 없이 반출 시 처벌은?", "exp": "N", "type": "P", "cat": "PENALTIES"},
    {"q": "수입면허 없이 판매용 사용시 제재", "exp": "O", "type": "AB", "cat": "PENALTIES"},
    {"q": "운영인 의무위반 처분", "exp": "P", "type": "AB", "cat": "PENALTIES"},
    {"q": "과태료 산정 기준", "exp": "AP", "type": "P", "cat": "PENALTIES"},
    {"q": "운영인 의무위반시 특허취소 되나요", "exp": "BA", "type": "P", "cat": "PENALTIES"},
    {"q": "보세전시장 폐쇄되는 경우", "exp": "BB", "type": "P", "cat": "PENALTIES"},

    # === 연락처 (CONTACT) ===
    {"q": "보세전시장 문의처가 어디?", "exp": "Q", "type": "P", "cat": "CONTACT"},
    {"q": "유니패스 장애 신고 어디로?", "exp": "R", "type": "P", "cat": "CONTACT"},
    {"q": "특허 담당부서 알려주세요", "exp": "S", "type": "AB", "cat": "CONTACT"},
    {"q": "관세 이의신청 절차", "exp": "AQ", "type": "P", "cat": "CONTACT"},
    {"q": "관세사 대행 가능?", "exp": "AX", "type": "P", "cat": "CONTACT"},

    # === 검사/특허침해 ===
    {"q": "보세전시장 물품검사 진행방식", "exp": "AY", "type": "P", "cat": "INSPECTION"},
    {"q": "위조품 발견하면 어떻게?", "exp": "AZ", "type": "P", "cat": "PATENT_INFRINGEMENT"},
    {"q": "모조품 적발시 처리", "exp": "AZ", "type": "P", "cat": "PATENT_INFRINGEMENT"},

    # === 엣지/모호 (EG) — 어휘는 비슷하나 의도가 명확한 케이스 ===
    {"q": "보세전시장이 뭔가요?", "exp": "A", "type": "EG", "cat": "GENERAL"},
    {"q": "보세전시장 정의 알려주세요", "exp": "A", "type": "EG", "cat": "GENERAL"},
    {"q": "전시품 외부반출 가능여부", "exp": "D", "type": "EG", "cat": "SAMPLE"},
    {"q": "보세창고와의 차이점", "exp": "T", "type": "EG", "cat": "GENERAL"},
    {"q": "보세전시장 종료 후 잔여물품", "exp": "W", "type": "EG", "cat": "IMPORT_EXPORT"},
    {"q": "보세전시장 사용 자격", "exp": "U", "type": "EG", "cat": "GENERAL"},

    # === 운영인 vs 운영자 표기 변형 ===
    {"q": "운영자가 갖춰야 할 조건", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영자의 자격요건", "exp": "AR", "type": "GR", "cat": "GENERAL"},

    # === 약어/구어체 ===
    {"q": "전시기간 중 물품바꿔도 됨?", "exp": "AM", "type": "P", "cat": "EXHIBITION"},
    {"q": "면허 없이 판매하면 어떻게됨", "exp": "O", "type": "P", "cat": "PENALTIES"},
    {"q": "특허 취소될 수 있는 경우들", "exp": "AK", "type": "P", "cat": "LICENSE"},
    {"q": "전시 종료 후 남은 물건은?", "exp": "W", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "보세전시장에서 판매한 후 결제는?", "exp": "AD", "type": "P", "cat": "SALES"},

    # === 추가 운영인-vs-시식 디스앰비귀에이션 ===
    {"q": "시식 식품 요건은 어떻게 되나요?", "exp": "E", "type": "EG", "cat": "FOOD_TASTING"},
    {"q": "시식용 식품 요건확인 받아야 하나요?", "exp": "E", "type": "EG", "cat": "FOOD_TASTING"},
]


async def run_query(ret: FAQRetriever, prep: Preprocessor, q: str):
    t0 = time.perf_counter()
    pq = await prep.process(q)
    hits, ex = await ret.retrieve(pq, top_k=3)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return hits, ex, elapsed_ms


async def main() -> None:
    with open("data/faq.json", encoding="utf-8") as f:
        faq = json.load(f)["items"]
    with open("data/golden_testset.json", encoding="utf-8") as f:
        golden = json.load(f)["items"]

    ret = FAQRetriever(faq)
    prep = Preprocessor()

    print("=" * 70)
    print("PART 1: 기존 골든셋 (100문항) 회귀 확인")
    print("=" * 70)
    golden_top1 = 0
    golden_top3 = 0
    golden_fails = []
    for i, item in enumerate(golden, 1):
        hits, ex, _ = await run_query(ret, prep, item["question"])
        top1 = hits[0].faq_id if hits else None
        top3 = [h.faq_id for h in hits]
        exp = item["expected_faq_id"]
        if top1 == exp:
            golden_top1 += 1
        if exp in top3:
            golden_top3 += 1
        else:
            golden_fails.append((i, item["question"], exp, top3))

    print(f"Top-1: {golden_top1}/100 = {golden_top1}%")
    print(f"Top-3: {golden_top3}/100 = {golden_top3}%")
    if golden_fails:
        print("\n[Top-3 미포함]")
        for i, q, exp, top3 in golden_fails:
            print(f"  #{i:3d} expected={exp} top3={top3}  Q={q}")
    else:
        print("[회귀 없음 — 100% 유지]")

    print()
    print("=" * 70)
    print(f"PART 2: 확장 챌린지셋 ({len(EXTENDED_TESTS)}문항)")
    print("=" * 70)

    ext_top1 = 0
    ext_top3 = 0
    by_type = defaultdict(lambda: [0, 0, 0])  # [n, top1, top3]
    by_cat = defaultdict(lambda: [0, 0, 0])
    rows = []
    fails_top1 = []

    for i, t in enumerate(EXTENDED_TESTS, 1):
        hits, ex, ms = await run_query(ret, prep, t["q"])
        top1 = hits[0].faq_id if hits else None
        top3 = [h.faq_id for h in hits]
        score = hits[0].score if hits else 0.0
        is_top1 = top1 == t["exp"]
        is_top3 = t["exp"] in top3
        if is_top1:
            ext_top1 += 1
        if is_top3:
            ext_top3 += 1
        by_type[t["type"]][0] += 1
        by_type[t["type"]][1] += int(is_top1)
        by_type[t["type"]][2] += int(is_top3)
        by_cat[t["cat"]][0] += 1
        by_cat[t["cat"]][1] += int(is_top1)
        by_cat[t["cat"]][2] += int(is_top3)
        if not is_top1:
            fails_top1.append((i, t, top1, top3, score, ex.chosen_via, ex.confidence_band))
        rows.append((i, t, top1, top3, score, ms, ex.chosen_via, ex.confidence_band, is_top1, is_top3))

    n = len(EXTENDED_TESTS)
    print(f"Top-1: {ext_top1}/{n} = {ext_top1/n*100:.1f}%")
    print(f"Top-3: {ext_top3}/{n} = {ext_top3/n*100:.1f}%")

    print("\n[유형별]")
    type_names = {"P": "Paraphrase", "AB": "Abbrev", "TY": "Typo", "EG": "Edge", "GR": "운영인 Guard"}
    for k, (tot, t1, t3) in sorted(by_type.items()):
        print(f"  {type_names.get(k,k):<14} {t1:>2}/{tot:<2} top-1={t1/tot*100:5.1f}%  top-3={t3/tot*100:5.1f}%")

    print("\n[카테고리별]")
    for k, (tot, t1, t3) in sorted(by_cat.items()):
        print(f"  {k:<22} {t1:>2}/{tot:<2} top-1={t1/tot*100:5.1f}%  top-3={t3/tot*100:5.1f}%")

    if fails_top1:
        print(f"\n[Top-1 실패 {len(fails_top1)}건]")
        for i, t, top1, top3, score, via, band in fails_top1:
            in3 = "(Top3 O)" if t["exp"] in top3 else "(Top3 X)"
            print(f"  #{i:3d} [{t['type']}/{t['cat']}] expected={t['exp']} got={top1} top3={top3} {in3}")
            print(f"        via={via} band={band} score={score:.3f}  Q={t['q']}")
    else:
        print("\n[Top-1 실패 없음]")

    print()
    print("=" * 70)
    print("PART 3: 운영인↔시식 디스앰비귀에이션 회귀 가드")
    print("=" * 70)
    guard_total = 0
    guard_pass = 0
    for r in rows:
        i, t, top1, top3, score, ms, via, band, t1_ok, _ = r
        if t["type"] != "GR":
            continue
        guard_total += 1
        status = "O" if t1_ok else "X"
        if t1_ok:
            guard_pass += 1
        print(f"  {status} #{i:3d} [{top1:>3}<-AR] via={via:<11} band={band:<6} score={score:.3f}  {t['q']}")
    print(f"\n  운영인 Guard: {guard_pass}/{guard_total} = {guard_pass/guard_total*100:.1f}%")

    print()
    print("=" * 70)
    print("PART 4: 전체 결과표 (확장셋)")
    print("=" * 70)
    print(f"  {'#':>3} {'결과':<4} {'유형':<3} {'기대':<4} {'실제':<4} {'스코어':<7} {'밴드':<7} {'ms':>5}  질문")
    for i, t, top1, top3, score, ms, via, band, t1_ok, _ in rows:
        mark = "O" if t1_ok else "X"
        q_short = t["q"][:60]
        print(f"  {i:>3} {mark:<4} {t['type']:<3} {t['exp']:<4} {(top1 or '-'):<4} {score:>6.3f} {band:<7} {ms:>4}ms  {q_short}")

    # 요약
    print()
    print("=" * 70)
    print("종합 요약")
    print("=" * 70)
    total_q = 100 + n
    total_t1 = golden_top1 + ext_top1
    total_t3 = golden_top3 + ext_top3
    print(f"  전체 문항: {total_q}")
    print(f"  Top-1: {total_t1}/{total_q} = {total_t1/total_q*100:.1f}%")
    print(f"  Top-3: {total_t3}/{total_q} = {total_t3/total_q*100:.1f}%")
    print(f"  - 골든셋(100):  Top-1 {golden_top1}%  Top-3 {golden_top3}%")
    print(f"  - 확장셋({n}):   Top-1 {ext_top1/n*100:.1f}%  Top-3 {ext_top3/n*100:.1f}%")
    print(f"  - 운영인 Guard: {guard_pass}/{guard_total} = {guard_pass/guard_total*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
