#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
챗봇 법령 적재 테스트
보세전시장 관련 질문으로 새로 적재된 법령 데이터 테스트
"""

import requests
import json
import time
import sys

from src.chatbot import BondedExhibitionChatbot


def test_policy_escalation_response_does_not_raise():
    chatbot = BondedExhibitionChatbot()
    response = chatbot._build_escalation_response_from_policy({
        "risk_level": "critical",
        "escalation_target": "local_customs",
        "disclaimers": ["최종 처리는 관할 세관 확인이 필요합니다."],
    })

    assert "고위험 민원" in response
    assert "관할 세관" in response
    assert "최종 처리는 관할 세관 확인이 필요합니다." in response


def test_chatbot():
    """챗봇 테스트"""
    base_url = "http://127.0.0.1:5099"
    
    # 테스트 질문 목록
    test_questions = [
        {
            "q": "보세전시장이란 무엇입니까?",
            "category": "정의"
        },
        {
            "q": "보세전시장에서 판매용 물품을 사용하려면 어떤 절차가 필요한가요?",
            "category": "판매용품"
        },
        {
            "q": "보세운송업자가 하는 역할은 무엇입니까?",
            "category": "운송업자"
        },
        {
            "q": "보세화물을 반입할 때 필요한 절차는?",
            "category": "반입절차"
        },
        {
            "q": "보세전시장의 회기가 종료된 후 물품은 어떻게 처리되나요?",
            "category": "폐회후처리"
        }
    ]
    
    print("[*] 챗봇 법령 적재 테스트 시작")
    print(f"[*] 서버: {base_url}\n")
    
    # 헬스 체크
    try:
        health = requests.get(f"{base_url}/api/health", timeout=3)
        if health.status_code == 200:
            health_data = health.json()
            print(f"[+] 서버 상태: OK")
            print(f"    - 버전: {health_data.get('version', 'N/A')}")
            print(f"    - FAQ 개수: {health_data.get('faq_count', 0)}\n")
        else:
            print(f"[!] 서버 응답 비정상: {health.status_code}")
            return
    except Exception as e:
        print(f"[!] 서버 연결 실패: {e}")
        print("[*] Flask 서버가 http://127.0.0.1:5099 에서 실행 중인지 확인하세요")
        return
    
    # 테스트 질문
    print("[*] 테스트 질문 전송 중...\n")
    for i, test in enumerate(test_questions, 1):
        print(f"[테스트 {i}] {test['category']}")
        print(f"  질문: {test['q']}")
        
        try:
            response = requests.post(
                f"{base_url}/api/chat",
                json={"query": test['q']},
                timeout=5
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    answer = data.get("response", data.get("answer", ""))
                    if answer:
                        # 응답 길이가 길면 일부만 표시
                        display_answer = answer[:150] + "..." if len(answer) > 150 else answer
                        print(f"  응답: {display_answer}")
                        print(f"  상태: ✓ 성공")
                    else:
                        print(f"  응답: (비어있음)")
                        print(f"  원본: {data}")
                except json.JSONDecodeError:
                    print(f"  응답 (텍스트): {response.text[:150]}")
            else:
                print(f"  상태: ✗ 오류 {response.status_code}")
                print(f"  응답: {response.text[:100]}")
        
        except requests.Timeout:
            print(f"  상태: ✗ 타임아웃")
        except Exception as e:
            print(f"  상태: ✗ {type(e).__name__}: {e}")
        
        print()
    
    # 법령 데이터 확인
    print("[*] 적재된 법령 조항 확인")
    try:
        from pathlib import Path
        legal_refs_path = Path("data/legal_references.json")
        if legal_refs_path.exists():
            with open(legal_refs_path, encoding="utf-8") as f:
                data = json.load(f)
                refs = data.get("references", [])
                print(f"  총 조항: {len(refs)}개")
                
                # 카테고리별 집계
                laws = {}
                for ref in refs:
                    law = ref.get("law_name", "Unknown")
                    laws[law] = laws.get(law, 0) + 1
                
                print(f"\n  법령별 조항 수:")
                for law, count in sorted(laws.items()):
                    print(f"    - {law}: {count}개")
        else:
            print("  [!] legal_references.json 파일 없음")
    except Exception as e:
        print(f"  [!] 오류: {e}")
    
    print("\n[+] 테스트 완료")

if __name__ == "__main__":
    test_chatbot()
