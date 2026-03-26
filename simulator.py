#!/usr/bin/env python3
"""보세전시장 민원응대 챗봇 시뮬레이터.

터미널에서 대화형으로 챗봇을 테스트할 수 있는 인터페이스입니다.

사용법:
    python simulator.py              # 대화형 모드
    python simulator.py --test       # 미리 정의된 시나리오 자동 테스트
    python simulator.py --query "질문"  # 단일 질문 테스트
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.chatbot import BondedExhibitionChatbot


SAMPLE_QUERIES = [
    "보세전시장이 무엇인가요?",
    "물품을 반입하려면 신고가 필요한가요?",
    "전시한 물품을 현장에서 바로 판매할 수 있나요?",
    "견본품으로 밖에 가져가도 되나요?",
    "시식용 식품을 들여오는 경우 요건확인은 생략되나요?",
    "보세전시장 특허기간은 어떻게 되나요?",
    "보세전시장 설치·운영 특허를 받으려면 어디를 봐야 하나요?",
    "UNI-PASS 시스템 오류가 발생했습니다",
    "유권해석을 요청합니다",
    "현장에서 즉시 인도 가능한가요?",
]


def run_interactive(chatbot: BondedExhibitionChatbot):
    """대화형 모드로 챗봇을 실행한다."""
    print("=" * 60)
    print("보세전시장 민원응대 챗봇 시뮬레이터")
    print("=" * 60)
    print()
    print(chatbot.get_persona())
    print()
    print("종료하려면 'quit', 'exit', 또는 'q'를 입력하세요.")
    print("-" * 60)

    while True:
        try:
            query = input("\n[민원인] ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n시뮬레이터를 종료합니다.")
            break

        if query.lower() in ("quit", "exit", "q", "종료"):
            print("\n시뮬레이터를 종료합니다.")
            break

        if not query:
            continue

        print()
        print("[챗봇]")
        response = chatbot.process_query(query)
        print(response)
        print("-" * 60)


def run_test_scenarios(chatbot: BondedExhibitionChatbot):
    """미리 정의된 시나리오를 자동 테스트한다."""
    print("=" * 60)
    print("챗봇 자동 테스트 시나리오")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print(f"\n{'='*60}")
        print(f"시나리오 {i}: {query}")
        print("-" * 60)

        response = chatbot.process_query(query)
        print(response)

        # 기본 검증: 답변이 비어있지 않고, 안내 문구가 포함되어야 함
        checks = []
        if response and len(response) > 10:
            checks.append(("답변 생성", True))
        else:
            checks.append(("답변 생성", False))

        if "안내:" in response or "안내용 설명" in response:
            checks.append(("면책 문구 포함", True))
        else:
            checks.append(("면책 문구 포함", False))

        print()
        for check_name, check_result in checks:
            status = "PASS" if check_result else "FAIL"
            print(f"  [{status}] {check_name}")
            if check_result:
                passed += 1
            else:
                failed += 1

    print(f"\n{'='*60}")
    print(f"결과: {passed} PASS / {failed} FAIL (총 {passed + failed} 검증)")
    print("=" * 60)

    return failed == 0


def run_single_query(chatbot: BondedExhibitionChatbot, query: str):
    """단일 질문을 테스트한다."""
    print(f"[질문] {query}")
    print()
    print("[답변]")
    response = chatbot.process_query(query)
    print(response)


def main():
    parser = argparse.ArgumentParser(description="보세전시장 민원응대 챗봇 시뮬레이터")
    parser.add_argument("--test", action="store_true", help="자동 테스트 시나리오 실행")
    parser.add_argument("--query", "-q", type=str, help="단일 질문 테스트")
    args = parser.parse_args()

    chatbot = BondedExhibitionChatbot()

    if args.test:
        success = run_test_scenarios(chatbot)
        sys.exit(0 if success else 1)
    elif args.query:
        run_single_query(chatbot, args.query)
    else:
        run_interactive(chatbot)


if __name__ == "__main__":
    main()
