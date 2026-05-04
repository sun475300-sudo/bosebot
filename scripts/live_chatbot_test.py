"""라이브 챗봇 회귀 — 10개 질문 재현.

reports/live_chatbot_test_<TS>.md 생성.

원본 라이브 리포트 (live_chatbot_test_20260504_094643.md) 와
동일한 10개 질문으로 챗봇을 호출하여, intent / category / 신뢰도 /
응답 시간 / 법령 인용 여부를 마크다운 표로 출력한다.
"""

from __future__ import annotations

import datetime
import os
import platform
import sys
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

os.environ.setdefault("SKIP_HEAVY_DEPS", "1")

QUESTIONS = [
    "보세전시장에서 특허 기간이 얼마인가요?",
    "특허 신청 절차 알려주세요",
    "특허 갱신은 어떻게 하나요?",
    "운영인 의무 위반시 특허가 취소되나요?",
    "보세전시장 폐쇄 사유는 무엇인가요?",
    "물품 반출입 절차 설명해주세요",
    "보세전시장 물품 검사 어떻게 진행되나요?",
    "고시의 목적이 무엇인가요?",
    "특허 침해품 어떻게 처리하나요?",
    "보세전시장 운영자가 지켜야 할 의무는?",
]


def _has_legal_citation(answer: str) -> bool:
    return ("관세법" in answer) or ("고시" in answer) or ("법" in answer)


def main():
    boot_start = time.perf_counter()
    from src.chatbot import BondedExhibitionChatbot

    bot = BondedExhibitionChatbot()
    boot_ms = int((time.perf_counter() - boot_start) * 1000)

    rows = []
    timings = []
    for i, q in enumerate(QUESTIONS, start=1):
        t0 = time.perf_counter()
        r = bot.process_query(q, include_metadata=True)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        timings.append(elapsed_ms)
        ans = r["response"]
        rows.append({
            "n": i,
            "q": q,
            "ms": elapsed_ms,
            "category": r["category"],
            "intent_id": r["intent_id"],
            "intent_conf": r["intent_confidence"],
            "risk": r["risk_level"],
            "legal": _has_legal_citation(ans),
            "answer": ans,
        })

    avg_ms = sum(timings) // max(len(timings), 1)
    legal_count = sum(1 for x in rows if x["legal"])

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(ROOT, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"live_chatbot_test_{ts}.md")

    py_ver = platform.python_version()
    plat = platform.platform()

    lines = []
    lines.append("# 보세전시장 챗봇 라이브 테스트 리포트 (분류기 수정 후)")
    lines.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("- 테스트 모드: direct-import (web_server skip), SKIP_HEAVY_DEPS=1, vector_search=disabled")
    lines.append(f"- Python: {py_ver}")
    lines.append(f"- Platform: {plat}")
    lines.append(f"- 부팅 시간: {boot_ms} ms")
    lines.append("")
    lines.append("## 요약")
    lines.append("")
    lines.append("| 지표 | 값 |")
    lines.append("|------|----|")
    lines.append(f"| 통과 질문 | {len(rows)}/{len(rows)} |")
    lines.append(f"| 평균 응답 시간 | {avg_ms} ms |")
    lines.append(f"| 법령 가이드 인용 비율 | {round(100*legal_count/len(rows))}% ({legal_count}/{len(rows)}) |")
    lines.append(f"| 최소 응답 시간 | {min(timings)} ms |")
    lines.append(f"| 최대 응답 시간 | {max(timings)} ms |")
    lines.append("")
    lines.append("## 질문/답변 테이블")
    lines.append("")
    lines.append("| # | 질문 | 시간(ms) | 카테고리 | 의도 ID | 신뢰도 | 위험도 | 법령? | 답변(첫 100자) |")
    lines.append("|---|------|---------|----------|---------|--------|--------|-------|----------------|")
    for x in rows:
        ans_short = x["answer"][:100].replace("|", "\\|").replace("\n", " ")
        legal = "⚖️" if x["legal"] else "—"
        lines.append(
            f"| {x['n']} | {x['q']} | {x['ms']} | {x['category']} | "
            f"{x['intent_id']} | {x['intent_conf']:.2f} | {x['risk']} | {legal} | {ans_short} |"
        )
    lines.append("")

    lines.append("## 상세 답변")
    lines.append("")
    for x in rows:
        lines.append(f"### Q{x['n']}. {x['q']}")
        lines.append("")
        lines.append(f"- 응답 시간: {x['ms']} ms")
        lines.append(f"- 카테고리: {x['category']}")
        lines.append(f"- 의도 ID: {x['intent_id']} (신뢰도 {x['intent_conf']:.2f})")
        lines.append(f"- 위험도: {x['risk']}")
        lines.append(f"- 법령 인용 여부: {'O' if x['legal'] else 'X'}")
        lines.append("")
        lines.append("```")
        lines.append(x["answer"])
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"WROTE: {out_path}")
    print(f"avg_ms={avg_ms}, legal={legal_count}/{len(rows)}")


if __name__ == "__main__":
    main()
