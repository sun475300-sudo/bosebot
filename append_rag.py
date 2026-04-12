import json
import os
import uuid

file_path = 'data/rag_documents.jsonl'

# Count existing
count = 0
with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        count += 1

start_id = count + 1

new_docs = [
    {
        "doc_id": f"RAG-{start_id:03d}",
        "title": "관세법 제190조: 보세전시장 요건",
        "source_type": "관세법",
        "source_name": "관세법",
        "content": "관세법 제190조 및 관련 세부 규정에 따르면, 보세전시장은 전시회 운용을 위해 외국물품을 보세상태로 전시할 수 있도록 세관장의 특허를 받은 구역이다. 보세전시장을 특허하려는 자는 특허신청서 외에 건축물관리대장 사본, 구역 도면, 사업계획서, 그리고 임대차계약서 등 시설 보유 현황과 사업 규모를 증빙하는 서류를 관체 관할 세관에 제출해야 한다. 담당 공무원은 법인등기사항증명서 등을 행정정보 공동이용 시스템을 통해 직접 확인한다.",
        "legal_citations": ["관세법", "보세전시장 운영에 관한 고시"],
        "keywords": ["관세법", "보세전시장", "서류", "특허신청서", "사업계획서"],
        "category": "보세전시장 설정 및 관리",
        "effective_date": "2024-01-01",
        "risk_level": "low"
    },
    {
        "doc_id": f"RAG-{start_id+1:03d}",
        "title": "관세법시행규칙: 보세전시장 특허 서류",
        "source_type": "관세법시행규칙",
        "source_name": "관세법시행규칙",
        "content": "관세법시행규칙에 의하면 보세구역 특허 시 필수적으로 제출해야 하는 서식과 절차가 명확히 기재되어 있다. 신청인은 보세구역 설치·운영 특허신청서(시행규칙 별지 서식)에 위치도와 도면을 필수적으로 첨부해야 하며, 행정관청은 접수된 서류의 진위와 현장 실사를 통해 적합성을 심사한다. 서류 제출 시 누락이 있을 경우 허가가 반려될 수 있으므로, 임원 인적사항과 전시장 평면도가 정확히 일치해야 한다.",
        "legal_citations": ["관세법시행규칙"],
        "keywords": ["관세법시행규칙", "특허", "서류", "도면", "위치도"],
        "category": "보세전시장 설정 및 관리",
        "effective_date": "2024-01-01",
        "risk_level": "medium"
    },
    {
        "doc_id": f"RAG-{start_id+2:03d}",
        "title": "보세운송에 관한 고시: 전시장 반입",
        "source_type": "보세운송에 관한 고시",
        "source_name": "보세운송에 관한 고시",
        "content": "보세운송에 관한 고시에서는 타 지역의 항만이나 공항에서 미통관 상태의 외국물품을 보세전시장으로 안전하게 이동시키는 보세운송 절차를 규정한다. 전시물품을 보세전시장으로 옮기기 위해서는 화주 또는 관세사가 관할 세관장에게 보세운송 신고를 해야 하며, 운송인은 반드시 세관장이 지정한 보세운송업자이어야 한다. 운송 중 물품의 도난이나 분실을 방지하기 위해 세관 고정을 받거나 전자추적장치(e-Seal)를 부착할 수 있다.",
        "legal_citations": ["보세운송에 관한 고시"],
        "keywords": ["보세운송", "보세운송업자", "반입", "항만", "전시물품"],
        "category": "보세운송", "effective_date": "2024-01-01", "risk_level": "medium"
    },
    {
        "doc_id": f"RAG-{start_id+3:03d}",
        "title": "관세법령시행령: 보세구역 특례",
        "source_type": "관세법령시행령",
        "source_name": "관세법시행령",
        "content": "관세법 시행령(관세법령시행령)은 보세전시장 운영 시 발생하는 특례 규정을 상세히 정의한다. 전시장에서 외국물품을 전시한 후 소모되거나 시식된 부분은 세관장의 사전 승인을 받아 관세를 면제 및 징수 면제 처리할 수 있다. 그러나 사전 승인 없이 전시기간 중 무단 반출되거나 소비된 경우에는, 관세법 위반으로 관세 추징과 동시에 과태료 혹은 고발 조치될 수 있다.",
        "legal_citations": ["관세법령시행령", "관세법 시행령"],
        "keywords": ["관세법령시행령", "특례", "소비", "면제", "과태료"],
        "category": "벌칙 및 처벌", "effective_date": "2024-01-01", "risk_level": "high"
    },
    {
        "doc_id": f"RAG-{start_id+4:03d}",
        "title": "ATA 까르네에 의한 일시수출입 통관에 관한 고시: 까르네 사용",
        "source_type": "ATA 까르네에 의한 일시수출입 통관에 관한 고시",
        "source_name": "ATA 까르네고시",
        "content": "ATA 까르네에 의한 일시수출입 통관에 관한 고시는 국제 관세 협약에 따라 수입 관세나 부가세 납부를 면제하고 무관세 통관증서(ATA Carnet)를 통해 전시 물품을 신속히 통관하는 절차를 명시한다. 보세전시장의 출품을 목적으로 하는 외국 화주가 까르네 증서를 발급받아 세관에 제시하면, 일반적인 수입신고서나 담보 제공 없이 일시 수입이 허용된다. 다만, 까르네 증서에 기재된 일시수입 유효기간 내에 반드시 물품을 전시장 밖으로 원상태 재수출해야 관세가 부과되지 않는다.",
        "legal_citations": ["ATA 까르네에 의한 일시수출입 통관에 관한 고시"],
        "keywords": ["ATA 까르네", "무관세", "일시수입", "재수출", "통관증서"],
        "category": "보세물품 관리", "effective_date": "2024-01-01", "risk_level": "high"
    },
    {
        "doc_id": f"RAG-{start_id+5:03d}",
        "title": "보세전시장 운영에 관한 고시: 전시 및 현장 판매",
        "source_type": "보세전시장 운영에 관한 고시",
        "source_name": "보세전시장 운영에 관한 고시",
        "content": "보세전시장 운영에 관한 고시는 전시장 내부에서의 판매 허가 기준을 별도로 정하고 있다. 일반적으로 보세물품은 전시 목적으로 반입되지만, 수입통관 절차를 거치지 않고 직접 판매가 가능한 특허를 추가로 받은 경우에 한해서 내국인 및 관광객에게 물품을 판매할 수 있다. 판매 시점에는 세관장이 지정한 현금등록기 및 판매관리 시스템을 사용해야 하며, 매일 판매 실적을 익일 오전까지 세관 통계에 연동해야 한다.",
        "legal_citations": ["보세전시장 운영에 관한 고시"],
        "keywords": ["운영고시", "판매", "통관", "현장판매", "실적보고"],
        "category": "보세전시장 운영", "effective_date": "2024-01-01", "risk_level": "medium"
    }
]

with open(file_path, 'a', encoding='utf-8') as f:
    for doc in new_docs:
        f.write(json.dumps(doc, ensure_ascii=False) + '\n')

print(f'{len(new_docs)} documents appended successfully.')
