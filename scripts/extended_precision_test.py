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
# 유형:
#   P  = paraphrase (어순/어휘 바꿈)
#   AB = abbreviation (단문/약어/명사구)
#   EG = edge/ambiguous (어휘는 비슷하나 의도가 명확)
#   GR = 운영인-guard (운영인 vs 시식식품 회귀가드)
#   CV = colloquial/conversational (구어체/반말)
#   NG = negation/조건문
#   TY = typo (오타/띄어쓰기 오류)
#   SC = scenario (상황형 질문)
EXTENDED_TESTS: list[dict] = [
    # ====================================================================
    # === 운영인 요건 회귀 가드 (AR) — 시식식품 E와 어휘 충돌 ===
    # ====================================================================
    {"q": "운영인의 요건을 알려줘", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 요건이 어떻게 되나요?", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 자격조건을 알고싶어요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인이 되기 위한 자격은?", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영자 요건이 뭔가요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "보세전시장 운영인 자격 알려주세요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 자격조건 궁금합니다", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영자가 갖춰야 할 조건", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영자의 자격요건", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "보세전시장 운영하려면 자격이 필요한가요?", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영인 자격 어떻게 따나요", "exp": "AR", "type": "GR", "cat": "GENERAL"},
    {"q": "운영자 등록 요건 알려줘", "exp": "AR", "type": "GR", "cat": "GENERAL"},

    # ====================================================================
    # === A: 보세전시장 정의 ===
    # ====================================================================
    {"q": "보세전시장이라는게 도대체 뭔지 설명해주세요", "exp": "A", "type": "P", "cat": "GENERAL"},
    {"q": "보세전시장이 뭔가요?", "exp": "A", "type": "EG", "cat": "GENERAL"},
    {"q": "보세전시장 정의 알려주세요", "exp": "A", "type": "EG", "cat": "GENERAL"},
    {"q": "보세전시장 의미가 뭡니까", "exp": "A", "type": "P", "cat": "GENERAL"},
    {"q": "보세전시장 개념 설명 좀", "exp": "A", "type": "CV", "cat": "GENERAL"},
    {"q": "bonded exhibition area 뜻 한국어로", "exp": "A", "type": "EG", "cat": "GENERAL"},
    {"q": "보세전시장이 어떤 곳이에요?", "exp": "A", "type": "P", "cat": "GENERAL"},

    # === T: 보세전시장 vs 보세창고 ===
    {"q": "보세창고랑 보세전시장 비교 좀", "exp": "T", "type": "CV", "cat": "GENERAL"},
    {"q": "보세창고와의 차이점", "exp": "T", "type": "EG", "cat": "GENERAL"},
    {"q": "보세창고 vs 보세전시장", "exp": "T", "type": "AB", "cat": "GENERAL"},
    {"q": "보세전시장과 보세창고 비교", "exp": "T", "type": "AB", "cat": "GENERAL"},
    {"q": "보세창고하고 보세전시장 다른점이 뭐예요?", "exp": "T", "type": "CV", "cat": "GENERAL"},

    # === U: 이용 자격 ===
    {"q": "보세전시장 이용 대상자는 누구인가요?", "exp": "U", "type": "P", "cat": "GENERAL"},
    {"q": "보세전시장 사용 자격", "exp": "U", "type": "EG", "cat": "GENERAL"},
    {"q": "누가 보세전시장을 쓸 수 있어요?", "exp": "U", "type": "CV", "cat": "GENERAL"},
    {"q": "보세전시장 이용 가능 대상", "exp": "U", "type": "AB", "cat": "GENERAL"},

    # === AC: 내국물품 전시 ===
    {"q": "내국물품 전시 가능여부", "exp": "AC", "type": "AB", "cat": "GENERAL"},
    {"q": "국산 물품도 전시할 수 있나요?", "exp": "AC", "type": "P", "cat": "GENERAL"},
    {"q": "보세전시장에 내국 제품 전시 OK?", "exp": "AC", "type": "CV", "cat": "GENERAL"},

    # === AJ: 행사 주최 준비 ===
    {"q": "행사 주최 시 준비사항", "exp": "AJ", "type": "AB", "cat": "GENERAL"},
    {"q": "보세전시장에서 행사 열려면 뭐 준비해야 해요?", "exp": "AJ", "type": "CV", "cat": "GENERAL"},
    {"q": "행사 개최 절차 안내", "exp": "AJ", "type": "P", "cat": "GENERAL"},

    # === BC: 고시 목적 ===
    {"q": "이 고시 목적이 뭐죠?", "exp": "BC", "type": "P", "cat": "GENERAL"},
    {"q": "보세전시장 고시는 왜 만들어졌나요?", "exp": "BC", "type": "P", "cat": "GENERAL"},
    {"q": "이 규정의 목적", "exp": "BC", "type": "AB", "cat": "GENERAL"},

    # ====================================================================
    # === IMPORT_EXPORT ===
    # ====================================================================
    # === B: 반출입 신고 의무 ===
    {"q": "물품 반입 반출 신고 의무가 있나요?", "exp": "B", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "반출입신고 안하면 안되나요?", "exp": "B", "type": "NG", "cat": "IMPORT_EXPORT"},
    {"q": "물품 들여올 때 신고해야해요?", "exp": "B", "type": "CV", "cat": "IMPORT_EXPORT"},
    {"q": "반입신고 필수인가요", "exp": "B", "type": "AB", "cat": "IMPORT_EXPORT"},

    # === V: 해외 재반송 ===
    {"q": "전시 끝난 물품 해외 재반송하려면?", "exp": "V", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "전시품 다시 외국으로 보내는 절차", "exp": "V", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "해외 반송 어떻게 해요", "exp": "V", "type": "CV", "cat": "IMPORT_EXPORT"},
    {"q": "전시 종료 후 반송 절차 알려줘", "exp": "V", "type": "P", "cat": "IMPORT_EXPORT"},

    # === W: 종료 후 잔여물품 ===
    {"q": "잔여물품 처리방법", "exp": "W", "type": "AB", "cat": "IMPORT_EXPORT"},
    {"q": "전시 종료 후 남은 물건은?", "exp": "W", "type": "CV", "cat": "IMPORT_EXPORT"},
    {"q": "전시 끝나고 남은 물품 어떡해요", "exp": "W", "type": "CV", "cat": "IMPORT_EXPORT"},
    {"q": "행사 후 잔존품 처리", "exp": "W", "type": "AB", "cat": "IMPORT_EXPORT"},

    # === AB: 세관 검사 ===
    {"q": "세관 검사 절차가 궁금해요 (보세전시장)", "exp": "AB", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "반입물품 세관검사 어떻게 진행되나요", "exp": "AB", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "보세전시장 반입품 검사절차", "exp": "AB", "type": "AB", "cat": "IMPORT_EXPORT"},

    # === AL: 가액 신고 ===
    {"q": "반입물품 가액신고 어떻게 하나요", "exp": "AL", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "물품 가격 신고 방법", "exp": "AL", "type": "AB", "cat": "IMPORT_EXPORT"},
    {"q": "전시품 가액은 어떻게 신고?", "exp": "AL", "type": "P", "cat": "IMPORT_EXPORT"},

    # === AS: 전시장 간 이동 ===
    {"q": "전시장 간 물품이동 가능여부 알려주세요", "exp": "AS", "type": "AB", "cat": "IMPORT_EXPORT"},
    {"q": "다른 보세전시장으로 옮길 수 있나요?", "exp": "AS", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "보세전시장 사이 물품 이전 가능?", "exp": "AS", "type": "P", "cat": "IMPORT_EXPORT"},
    {"q": "전시장간 물품 이송 절차", "exp": "AS", "type": "AB", "cat": "IMPORT_EXPORT"},

    # ====================================================================
    # === SALES ===
    # ====================================================================
    # === C: 현장 판매 ===
    {"q": "전시장에서 즉시 판매 가능?", "exp": "C", "type": "P", "cat": "SALES"},
    {"q": "보세전시장 현장판매 됨?", "exp": "C", "type": "CV", "cat": "SALES"},
    {"q": "전시한 물품 그자리에서 팔 수 있어요?", "exp": "C", "type": "CV", "cat": "SALES"},

    # === X: 계약 후 통관 ===
    {"q": "계약만 먼저 하고 통관은 나중에 가능?", "exp": "X", "type": "P", "cat": "SALES"},
    {"q": "판매계약 체결 후 통관 절차", "exp": "X", "type": "P", "cat": "SALES"},
    {"q": "계약 먼저 → 인도 나중 가능?", "exp": "X", "type": "CV", "cat": "SALES"},

    # === AD: 판매대금 정산 ===
    {"q": "판매대금 정산 방법", "exp": "AD", "type": "AB", "cat": "SALES"},
    {"q": "보세전시장 판매 결제는 어떻게?", "exp": "AD", "type": "P", "cat": "SALES"},
    {"q": "판매 대금 수금/정산 방법", "exp": "AD", "type": "AB", "cat": "SALES"},
    {"q": "전시품 판매 후 대금 정산 절차", "exp": "AD", "type": "P", "cat": "SALES"},

    # === AE: 수입면허 신청 ===
    {"q": "수입면허 신청 절차 (판매전)", "exp": "AE", "type": "P", "cat": "SALES"},
    {"q": "판매 전 수입면허 어디서 받나요", "exp": "AE", "type": "P", "cat": "SALES"},
    {"q": "수입면허 발급 방법", "exp": "AE", "type": "AB", "cat": "SALES"},

    # ====================================================================
    # === SAMPLE ===
    # ====================================================================
    # === D: 견본품 외부 반출 ===
    {"q": "샘플 외부반출 가능여부", "exp": "D", "type": "AB", "cat": "SAMPLE"},
    {"q": "전시품 외부반출 가능여부", "exp": "D", "type": "EG", "cat": "SAMPLE"},
    {"q": "견본품 밖으로 가져갈 수 있어요?", "exp": "D", "type": "CV", "cat": "SAMPLE"},
    {"q": "전시 샘플 반출 OK?", "exp": "D", "type": "CV", "cat": "SAMPLE"},

    # === Z: 견본품 관세 ===
    {"q": "견본품 관세 부과되나요?", "exp": "Z", "type": "P", "cat": "SAMPLE"},
    {"q": "샘플 반출 시 세금", "exp": "Z", "type": "AB", "cat": "SAMPLE"},
    {"q": "견본품에도 관세 내야 하나요?", "exp": "Z", "type": "P", "cat": "SAMPLE"},

    # === M: 견본품 반출 허가 신청 ===
    {"q": "샘플 반출 허가 신청처가 어디인가요", "exp": "M", "type": "P", "cat": "SAMPLE"},
    {"q": "견본품 반출허가 어디에 신청?", "exp": "M", "type": "P", "cat": "SAMPLE"},
    {"q": "샘플 외부 반출 허가 신청 방법", "exp": "M", "type": "P", "cat": "SAMPLE"},

    # === AF: 견본품 수량 제한 ===
    {"q": "견본품 수량 한도", "exp": "AF", "type": "AB", "cat": "SAMPLE"},
    {"q": "샘플 몇개까지 반출가능?", "exp": "AF", "type": "CV", "cat": "SAMPLE"},
    {"q": "견본품 반출 수량 상한", "exp": "AF", "type": "AB", "cat": "SAMPLE"},

    # === AG: 견본품 반환 의무 ===
    {"q": "견본품 반출 후 다시 돌려놔야 하나요", "exp": "AG", "type": "P", "cat": "SAMPLE"},
    {"q": "샘플 반환 의무 있나요", "exp": "AG", "type": "AB", "cat": "SAMPLE"},
    {"q": "견본품 외부반출 후 회수 필요?", "exp": "AG", "type": "P", "cat": "SAMPLE"},

    # ====================================================================
    # === FOOD_TASTING ===
    # ====================================================================
    # === E: 시식 식품 요건확인 ===
    {"q": "시식 식품 요건확인 면제되는지", "exp": "E", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식 식품 요건은 어떻게 되나요?", "exp": "E", "type": "EG", "cat": "FOOD_TASTING"},
    {"q": "시식용 식품 요건확인 받아야 하나요?", "exp": "E", "type": "EG", "cat": "FOOD_TASTING"},
    {"q": "시식 식품 세관장확인 면제?", "exp": "E", "type": "AB", "cat": "FOOD_TASTING"},
    {"q": "시식용 식품 검역요건 면제될까요", "exp": "E", "type": "P", "cat": "FOOD_TASTING"},

    # === Y: 시식 식품 사후처리 ===
    {"q": "시식 후 남은 식품 처리법", "exp": "Y", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식하고 남은 음식 어떻게 처리?", "exp": "Y", "type": "CV", "cat": "FOOD_TASTING"},
    {"q": "시식 행사 종료 후 식품 처리", "exp": "Y", "type": "P", "cat": "FOOD_TASTING"},

    # === AH: 시식 식품 수량 ===
    {"q": "시식 식품 반입수량 제한 있어요?", "exp": "AH", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식용 식품 얼마나 반입가능?", "exp": "AH", "type": "CV", "cat": "FOOD_TASTING"},
    {"q": "시식 식품 수량한도", "exp": "AH", "type": "AB", "cat": "FOOD_TASTING"},

    # === AI: 시식 사전신고 ===
    {"q": "시식행사 사전신고 의무?", "exp": "AI", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식 행사 전에 신고해야 하나요", "exp": "AI", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식 사전 신고 절차", "exp": "AI", "type": "AB", "cat": "FOOD_TASTING"},

    # === AV: 시식 식품 라벨 ===
    {"q": "시식 식품 라벨 표기 의무", "exp": "AV", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식용 식품 한글표기 필요?", "exp": "AV", "type": "P", "cat": "FOOD_TASTING"},
    {"q": "시식식품 한글 라벨 부착", "exp": "AV", "type": "AB", "cat": "FOOD_TASTING"},

    # ====================================================================
    # === LICENSE ===
    # ====================================================================
    # === F: 특허기간 ===
    {"q": "특허기간 얼마나 되나요", "exp": "F", "type": "AB", "cat": "LICENSE"},
    {"q": "보세전시장 특허는 몇 년인가요", "exp": "F", "type": "P", "cat": "LICENSE"},
    {"q": "특허기간 며칠이에요?", "exp": "F", "type": "CV", "cat": "LICENSE"},

    # === G: 특허 신청 근거 ===
    {"q": "특허신청 근거 어디 봐야하나요", "exp": "G", "type": "P", "cat": "LICENSE"},
    {"q": "보세전시장 특허 받으려면 어떤 법령?", "exp": "G", "type": "P", "cat": "LICENSE"},
    {"q": "특허 신청 근거 법령", "exp": "G", "type": "AB", "cat": "LICENSE"},

    # === AA: 특허 갱신 ===
    {"q": "특허 갱신 가능?", "exp": "AA", "type": "CV", "cat": "LICENSE"},
    {"q": "보세전시장 특허 연장 신청", "exp": "AA", "type": "AB", "cat": "LICENSE"},
    {"q": "특허기간 만료 후 연장 가능여부", "exp": "AA", "type": "P", "cat": "LICENSE"},

    # === AK: 특허 취소 사유 ===
    {"q": "특허취소 사유는?", "exp": "AK", "type": "AB", "cat": "LICENSE"},
    {"q": "특허 취소될 수 있는 경우들", "exp": "AK", "type": "P", "cat": "LICENSE"},
    {"q": "어떤 경우에 특허가 취소되나요?", "exp": "AK", "type": "P", "cat": "LICENSE"},

    # === AT: 특허신청 수수료 ===
    {"q": "특허신청 수수료 있나요", "exp": "AT", "type": "P", "cat": "LICENSE"},
    {"q": "보세전시장 특허비용", "exp": "AT", "type": "AB", "cat": "LICENSE"},
    {"q": "특허 신청 시 수수료 얼마?", "exp": "AT", "type": "CV", "cat": "LICENSE"},

    # ====================================================================
    # === EXHIBITION ===
    # ====================================================================
    # === H: 전시 가능 물품 제한 ===
    {"q": "전시품 종류 제한", "exp": "H", "type": "AB", "cat": "EXHIBITION"},
    {"q": "전시할 수 있는 물품에 제한 있나요?", "exp": "H", "type": "P", "cat": "EXHIBITION"},
    {"q": "전시 못하는 물품도 있어요?", "exp": "H", "type": "CV", "cat": "EXHIBITION"},

    # === I: 장치 물품 사용 범위 ===
    {"q": "장치된 물품 사용범위", "exp": "I", "type": "AB", "cat": "EXHIBITION"},
    {"q": "보세전시장에 둔 물품 어디까지 사용 가능?", "exp": "I", "type": "P", "cat": "EXHIBITION"},
    {"q": "장치물품 사용 범위 한도", "exp": "I", "type": "AB", "cat": "EXHIBITION"},

    # === J: 시연/데모 ===
    {"q": "데모 시연 가능?", "exp": "J", "type": "CV", "cat": "EXHIBITION"},
    {"q": "전시장에서 시연해도 되나요?", "exp": "J", "type": "P", "cat": "EXHIBITION"},
    {"q": "보세전시장 데모 행사 가능?", "exp": "J", "type": "P", "cat": "EXHIBITION"},

    # === AM: 전시 중 물품 교체 ===
    {"q": "전시 중 물품 교체 가능?", "exp": "AM", "type": "P", "cat": "EXHIBITION"},
    {"q": "전시기간 중 물품바꿔도 됨?", "exp": "AM", "type": "CV", "cat": "EXHIBITION"},
    {"q": "전시 도중 다른 물품으로 교체 가능여부", "exp": "AM", "type": "P", "cat": "EXHIBITION"},

    # === AN: 보관 주의사항 ===
    {"q": "전시장 보관 주의사항", "exp": "AN", "type": "AB", "cat": "EXHIBITION"},
    {"q": "보세전시장 내 물품 보관 시 유의점", "exp": "AN", "type": "P", "cat": "EXHIBITION"},
    {"q": "전시장 안전 관리 사항", "exp": "AN", "type": "P", "cat": "EXHIBITION"},

    # === AU: 촬영/홍보 활동 ===
    {"q": "전시장 사진촬영/홍보 활동 가능?", "exp": "AU", "type": "P", "cat": "EXHIBITION"},
    {"q": "전시장에서 사진 찍어도 돼요?", "exp": "AU", "type": "CV", "cat": "EXHIBITION"},
    {"q": "보세전시장 홍보 활동 허용여부", "exp": "AU", "type": "P", "cat": "EXHIBITION"},

    # ====================================================================
    # === DOCUMENTS ===
    # ====================================================================
    # === K: 반출입신고서 ===
    {"q": "반출입신고서 양식이 뭔가요", "exp": "K", "type": "P", "cat": "DOCUMENTS"},
    {"q": "보세전시장 반출입 신고서류", "exp": "K", "type": "AB", "cat": "DOCUMENTS"},
    {"q": "반출입신고서 어떤 서류인가요", "exp": "K", "type": "P", "cat": "DOCUMENTS"},

    # === L: 특허신청 서류 ===
    {"q": "특허신청 시 제출서류 목록", "exp": "L", "type": "P", "cat": "DOCUMENTS"},
    {"q": "특허 신청 첨부서류", "exp": "L", "type": "AB", "cat": "DOCUMENTS"},
    {"q": "보세전시장 특허신청서류 안내", "exp": "L", "type": "P", "cat": "DOCUMENTS"},

    # === AO: 수입면허 신청서류 ===
    {"q": "수입면허 신청서류", "exp": "AO", "type": "AB", "cat": "DOCUMENTS"},
    {"q": "수입면허 신청 시 필요 문서", "exp": "AO", "type": "P", "cat": "DOCUMENTS"},
    {"q": "수입면허 첨부서류 목록", "exp": "AO", "type": "AB", "cat": "DOCUMENTS"},

    # === AW: 운영 종료 보고서 ===
    {"q": "운영 종료 보고서 제출 방법", "exp": "AW", "type": "P", "cat": "DOCUMENTS"},
    {"q": "보세전시장 폐쇄 보고 어떻게?", "exp": "AW", "type": "CV", "cat": "DOCUMENTS"},
    {"q": "전시장 운영종료 신고", "exp": "AW", "type": "AB", "cat": "DOCUMENTS"},

    # ====================================================================
    # === PENALTIES ===
    # ====================================================================
    # === N: 무허가 반출 처벌 ===
    {"q": "허가 없이 반출 시 처벌은?", "exp": "N", "type": "P", "cat": "PENALTIES"},
    {"q": "무허가 반출 시 제재", "exp": "N", "type": "AB", "cat": "PENALTIES"},
    {"q": "허가 안받고 물품 빼면 어떻게 됨?", "exp": "N", "type": "CV", "cat": "PENALTIES"},

    # === O: 무면허 판매 ===
    {"q": "수입면허 없이 판매용 사용시 제재", "exp": "O", "type": "AB", "cat": "PENALTIES"},
    {"q": "면허 없이 판매하면 어떻게됨", "exp": "O", "type": "CV", "cat": "PENALTIES"},
    {"q": "수입면허 미취득 판매 처벌", "exp": "O", "type": "AB", "cat": "PENALTIES"},

    # === P: 운영인 의무 위반 처분 ===
    {"q": "운영인 의무위반 처분", "exp": "P", "type": "AB", "cat": "PENALTIES"},
    {"q": "운영인이 의무 어기면 어떤 처분?", "exp": "P", "type": "P", "cat": "PENALTIES"},
    {"q": "운영자 위반행위 제재", "exp": "P", "type": "AB", "cat": "PENALTIES"},

    # === AP: 과태료 ===
    {"q": "과태료 산정 기준", "exp": "AP", "type": "P", "cat": "PENALTIES"},
    {"q": "과태료 얼마인가요?", "exp": "AP", "type": "CV", "cat": "PENALTIES"},
    {"q": "과태료 부과 금액", "exp": "AP", "type": "AB", "cat": "PENALTIES"},

    # === BA: 의무위반 특허취소 ===
    {"q": "운영인 의무위반시 특허취소 되나요", "exp": "BA", "type": "P", "cat": "PENALTIES"},
    {"q": "의무위반하면 특허 잃나요?", "exp": "BA", "type": "CV", "cat": "PENALTIES"},
    {"q": "운영인 위반 → 특허취소 가능여부", "exp": "BA", "type": "P", "cat": "PENALTIES"},

    # === BB: 폐쇄 사유 ===
    {"q": "보세전시장 폐쇄되는 경우", "exp": "BB", "type": "P", "cat": "PENALTIES"},
    {"q": "어떤 경우에 폐쇄되나요?", "exp": "BB", "type": "P", "cat": "PENALTIES"},
    {"q": "보세전시장 강제폐쇄 사유", "exp": "BB", "type": "AB", "cat": "PENALTIES"},

    # ====================================================================
    # === CONTACT ===
    # ====================================================================
    # === Q: 일반 문의처 ===
    {"q": "보세전시장 문의처가 어디?", "exp": "Q", "type": "CV", "cat": "CONTACT"},
    {"q": "관련 문의 어디로 연락?", "exp": "Q", "type": "CV", "cat": "CONTACT"},
    {"q": "보세전시장 관련 안내전화", "exp": "Q", "type": "AB", "cat": "CONTACT"},

    # === R: UNI-PASS ===
    {"q": "유니패스 장애 신고 어디로?", "exp": "R", "type": "P", "cat": "CONTACT"},
    {"q": "UNI-PASS 오류 시 연락처", "exp": "R", "type": "AB", "cat": "CONTACT"},
    {"q": "유니패스 안될때 어디 문의?", "exp": "R", "type": "CV", "cat": "CONTACT"},

    # === S: 특허 담당부서 ===
    {"q": "특허 담당부서 알려주세요", "exp": "S", "type": "AB", "cat": "CONTACT"},
    {"q": "보세전시장 특허 부서 어디?", "exp": "S", "type": "CV", "cat": "CONTACT"},
    {"q": "특허 관련 담당과는?", "exp": "S", "type": "P", "cat": "CONTACT"},

    # === AQ: 이의신청 ===
    {"q": "관세 이의신청 절차", "exp": "AQ", "type": "P", "cat": "CONTACT"},
    {"q": "관세 불복 어떻게 하나요?", "exp": "AQ", "type": "P", "cat": "CONTACT"},
    {"q": "관세처분 이의제기 방법", "exp": "AQ", "type": "AB", "cat": "CONTACT"},

    # === AX: 관세사 대행 ===
    {"q": "관세사 대행 가능?", "exp": "AX", "type": "P", "cat": "CONTACT"},
    {"q": "관세사에게 위임해도 되나요", "exp": "AX", "type": "P", "cat": "CONTACT"},
    {"q": "관세사 대리 신청 가능여부", "exp": "AX", "type": "AB", "cat": "CONTACT"},

    # ====================================================================
    # === INSPECTION / PATENT_INFRINGEMENT ===
    # ====================================================================
    {"q": "보세전시장 물품검사 진행방식", "exp": "AY", "type": "P", "cat": "INSPECTION"},
    {"q": "물품검사 어떻게 받나요", "exp": "AY", "type": "CV", "cat": "INSPECTION"},
    {"q": "보세전시장 검사절차", "exp": "AY", "type": "AB", "cat": "INSPECTION"},

    {"q": "위조품 발견하면 어떻게?", "exp": "AZ", "type": "P", "cat": "PATENT_INFRINGEMENT"},
    {"q": "모조품 적발시 처리", "exp": "AZ", "type": "P", "cat": "PATENT_INFRINGEMENT"},
    {"q": "짝퉁 발견시 신고 절차", "exp": "AZ", "type": "CV", "cat": "PATENT_INFRINGEMENT"},
    {"q": "특허침해 의심 물품 처리", "exp": "AZ", "type": "AB", "cat": "PATENT_INFRINGEMENT"},

    # ====================================================================
    # === 시나리오 (SC) — 실제 사용자 상황 시뮬레이션 ===
    # ====================================================================
    {"q": "처음 보세전시장 신청하려는데 뭐부터 봐야 할까요", "exp": "G", "type": "SC", "cat": "LICENSE"},
    {"q": "전시 행사 진행중인데 물품을 더 들여와도 되나요", "exp": "AM", "type": "SC", "cat": "EXHIBITION"},
    {"q": "행사 끝났는데 남은 물품 처리가 고민이에요", "exp": "W", "type": "SC", "cat": "IMPORT_EXPORT"},
    {"q": "외국 바이어가 사겠다는데 통관 안하고 계약만 먼저 가능한가요", "exp": "X", "type": "SC", "cat": "SALES"},
    {"q": "시식코너 운영하려는데 사전에 신고하나요", "exp": "AI", "type": "SC", "cat": "FOOD_TASTING"},
    {"q": "운영하다가 특허기간 만료되는데 연장신청 어떻게", "exp": "AA", "type": "SC", "cat": "LICENSE"},
    {"q": "관세사한테 맡기고 싶은데 가능한지", "exp": "AX", "type": "SC", "cat": "CONTACT"},
    {"q": "행사장에서 위조품 발견했어요. 어떻게 처리?", "exp": "AZ", "type": "SC", "cat": "PATENT_INFRINGEMENT"},
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
    type_names = {
        "P": "Paraphrase",
        "AB": "Abbrev",
        "TY": "Typo",
        "EG": "Edge",
        "GR": "운영인 Guard",
        "CV": "Colloquial",
        "NG": "Negation",
        "SC": "Scenario",
    }
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
