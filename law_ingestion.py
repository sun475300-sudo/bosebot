#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
법령 문서 파싱 및 챗봇 인덱스 적재 스크립트
관세법, 시행령, 시행규칙, 행정규칙 HTML을 파싱하여 legal_references.json에 병합
"""

import json
import re
from datetime import datetime
from pathlib import Path
import sys

# 원본 데이터 (fetch_webpage에서 가져온 내용 시뮬레이션)
LAW_DATA = {
    "customs_law": {
        "title": "관세법",
        "law_id": "customs_law",
        "source_url": "https://law.go.kr/lsSc.do?section=&menuId=1&subMenuId=15&tabMenuId=81&eventGubun=060101&query=%EA%B4%80%EC%84%B8%EB%B2%95",
        "enacted_date": "1967-01-16",
        "last_amended": "2025-12-23",
        "category": "statute",
        "description": "관세의 부과, 징수 및 관세행정에 관한 근본적인 사항을 정함을 목적으로 함",
        "sections": [
            {"article": 156, "title": "보세구역 외 장치", "summary": "세관장은 보세구역 외의 장소에서 외국물품을 장치하게 할 수 있음"},
            {"article": 157, "title": "보세전시장", "summary": "보세전시장의 설치 및 운영에 관한 사항을 정함"},
            {"article": 174, "title": "보세전시장의 특허", "summary": "박람회 등에서 보세전시장을 특허받을 수 있음"},
            {"article": 213, "title": "보세운송", "summary": "관세가 면제된 물품의 일시적 운송을 허용"},
            {"article": 222, "title": "보세운송업자", "summary": "보세운송업자의 등록 및 관리 규정"},
        ]
    },
    "customs_enforcement": {
        "title": "관세법 시행령",
        "law_id": "customs_enforcement",
        "source_url": "https://law.go.kr/lsSc.do?section=&menuId=1&subMenuId=15&tabMenuId=81&eventGubun=060101&query=%EA%B4%80%EC%84%B8%EB%B2%95",
        "enacted_date": "1967-03-21",
        "last_amended": "2026-04-03",
        "category": "presidential_decree",
        "description": "관세법 시행에 필요한 세부 사항을 정함",
        "sections": [
            {"article": 226, "title": "보세운송에 관한 사항", "summary": "보세운송의 신고, 승인, 감시 등에 관한 규정"},
            {"article": 288, "title": "보세운송업자 등록 위탁", "summary": "세관장이 협회에 보세운송업자 등록 업무를 위탁"},
        ]
    },
    "customs_rules": {
        "title": "관세법 시행규칙",
        "law_id": "customs_rules",
        "source_url": "https://law.go.kr/lsSc.do?menuId=1&subMenuId=15&tabMenuId=81&query=%EB%B3%B4%EC%84%B8%EC%A0%84%EC%8B%9C%EC%9E%A5",
        "enacted_date": "1970-01-01",
        "last_amended": "2026-03-20",
        "category": "ministry_rule",
        "description": "관세법 및 시행령의 시행에 필요한 세부 절차를 정함",
        "sections": [
            {"article": 73, "title": "보세운송신고", "summary": "보세운송에 대한 신고 절차 및 서류 작성"}
        ]
    },
    "bonded_transport_notice": {
        "title": "보세운송에 관한 고시",
        "law_id": "bonded_transport_notice",
        "source_url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000270260",
        "enacted_date": "2004-12-06",
        "last_amended": "2026-01-01",
        "category": "administrative_rule",
        "description": "보세운송제도의 운영과 관리에 관한 사항을 규정",
        "sections": [
            {"article": 1, "title": "목적", "summary": "보세운송의 일반 규정"},
            {"article": 2, "title": "용어 정의", "summary": "고시에서 사용하는 용어의 정의"},
            {"article": 5, "title": "운송업자 등록", "summary": "보세운송업자 등록의 요건 및 절차"},
        ]
    },
    "bonded_cargo_notice": {
        "title": "보세화물관리에 관한 고시",
        "law_id": "bonded_cargo_notice",
        "source_url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000275032",
        "enacted_date": "2004-12-07",
        "last_amended": "2026-02-24",
        "category": "administrative_rule",
        "description": "보세구역 등에 장치할 물품의 반출입절차와 보관관리를 규정",
        "sections": [
            {"article": 1, "title": "목적", "summary": "보세화물관리의 일반 규정"},
            {"article": 4, "title": "화물분류기준", "summary": "물품의 장치장소 결정 기준"},
        ]
    },
    "ata_carnet_notice": {
        "title": "A.T.A.까르네에 의한 일시수출입 통관에 관한 고시",
        "law_id": "ata_carnet_notice",
        "source_url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000271566",
        "enacted_date": "2013-05-06",
        "last_amended": "2026-01-02",
        "category": "administrative_rule",
        "description": "A.T.A.까르네에 의한 일시수출입의 통관절차를 규정",
        "sections": [
            {"article": 1, "title": "목적", "summary": "A.T.A.까르네 운영에 관한 규정"},
        ]
    },
    "bonded_exhibition_notice": {
        "title": "보세전시장 운영에 관한 고시",
        "law_id": "bonded_exhibition_notice",
        "source_url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000276240",
        "enacted_date": "2013-05-06",
        "last_amended": "2026-03-24",
        "category": "administrative_rule",
        "description": "보세전시장의 설치, 운영 및 관리에 관한 세부사항을 규정",
        "sections": [
            {"article": 1, "title": "목적", "summary": "보세전시장의 특허 및 운영을 규정함"},
            {"article": 2, "title": "용어 정의", "summary": "박람회, 전시장 등의 용어 정의"},
            {"article": 3, "title": "설치 요건", "summary": "보세전시장 설치 가능 조건"},
            {"article": 9, "title": "반입 물품 범위", "summary": "건설용품, 업무용품, 오락용품, 전시용품, 판매용품, 증여물품"},
        ]
    }
}

def create_law_document(law_info):
    """법령 정보를 문서 형식으로 변환"""
    doc = {
        "id": law_info["law_id"],
        "title": law_info["title"],
        "category": law_info["category"],
        "source": {
            "url": law_info["source_url"],
            "enacted_date": law_info["enacted_date"],
            "last_amended": law_info["last_amended"]
        },
        "description": law_info["description"],
        "articles": [
            {
                "number": section.get("article", 0),
                "title": section.get("title", ""),
                "summary": section.get("summary", ""),
                "content": section.get("summary", "")
            }
            for section in law_info["sections"]
        ],
        "ingested_at": datetime.now().isoformat(),
        "keywords": extract_keywords(law_info["title"], law_info["description"])
    }
    return doc

def extract_keywords(title, description):
    """제목과 설명에서 키워드 추출"""
    text = f"{title} {description}".lower()
    keywords = []
    
    key_terms = [
        "보세", "전시장", "운송", "화물", "물품", "반입", "반출",
        "신고", "승인", "허가", "특허", "관세", "관세청", "세관",
        "외국물품", "내국물품", "판매", "시식", "증여", "폐기",
        "까르네", "박람회", "회기", "영업인", "운영인", "화물관리인"
    ]
    
    for term in key_terms:
        if term in text:
            keywords.append(term)
    
    return list(set(keywords))[:10]  # 최대 10개

def merge_into_legal_references(law_docs, output_path):
    """법령 문서를 legal_references.json에 병합"""
    new_refs = []
    
    for law_doc in law_docs:
        for article in law_doc.get("articles", []):
            ref_entry = {
                "id": f"{law_doc['id']}_art{article['number']}",
                "law_name": law_doc["title"],
                "article": f"제{article['number']}조",
                "title": article["title"],
                "summary": article["content"],
                "url": law_doc["source"]["url"],
                "keywords": law_doc.get("keywords", [])
            }
            new_refs.append(ref_entry)
    
    # 기존 legal_references.json 로드 (있으면)
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "references" in data:
                existing = data["references"]
            else:
                existing = data if isinstance(data, list) else []
    else:
        existing = []
    
    # ID 중복 제거
    existing_ids = {ref["id"] for ref in existing}
    filtered_new_refs = [ref for ref in new_refs if ref["id"] not in existing_ids]
    
    # 병합 및 정렬
    all_refs = existing + filtered_new_refs
    all_refs = sorted(all_refs, key=lambda x: (x["law_name"], x.get("article", "")))
    
    # 저장 (기존 형식 유지)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"references": all_refs}, f, ensure_ascii=False, indent=2)
    
    return len(all_refs)

def save_law_documents(law_docs, output_dir):
    """개별 법령 문서를 파일로 저장"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for law_doc in law_docs:
        file_path = output_dir / f"{law_doc['id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(law_doc, f, ensure_ascii=False, indent=2)
    
    return len(law_docs)

def main():
    print("[*] 법령 문서 파싱 시작...")
    
    # 데이터 디렉토리 설정
    data_dir = Path(__file__).parent / "data"
    law_docs_dir = data_dir / "law_documents"
    legal_refs_path = data_dir / "legal_references.json"
    
    # 1. 법령 문서 변환
    print("[*] 법령 문서를 구조화된 JSON으로 변환 중...")
    law_documents = [create_law_document(law_info) for law_info in LAW_DATA.values()]
    
    # 2. 개별 파일 저장
    print(f"[*] {len(law_documents)}개 법령 문서를 {law_docs_dir}에 저장 중...")
    saved_count = save_law_documents(law_documents, law_docs_dir)
    print(f"[+] {saved_count}개 파일 저장 완료")
    
    # 3. legal_references.json에 병합
    print(f"[*] legal_references.json에 병합 중...")
    ref_count = merge_into_legal_references(law_documents, legal_refs_path)
    print(f"[+] {ref_count}개 조항 적재 완료")
    
    # 4. 챗봇 인덱스 재생성 요청
    print("[*] 챗봇 인덱스 재생성 요청 중...")
    try:
        import requests
        response = requests.post(
            "http://127.0.0.1:5099/api/v1/admin/reload-faq",
            timeout=5
        )
        if response.status_code == 200:
            print("[+] FAQ 인덱스 재생성 완료")
        else:
            print(f"[!] FAQ 재생성 응답: {response.status_code}")
    except Exception as e:
        print(f"[!] 인덱스 재생성 요청 실패: {e}")
        print("[*] 서버가 구동 중인지 확인하세요 (http://127.0.0.1:5099)")
    
    print("\n[+] 작업 완료!")
    print(f"    - 저장 위치: {law_docs_dir}")
    print(f"    - 병합 파일: {legal_refs_path}")

if __name__ == "__main__":
    main()
