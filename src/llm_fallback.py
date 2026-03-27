"""LLM 하이브리드 폴백 모듈.

키워드 매칭 실패 시 LLM API를 호출하여 답변을 생성하는 폴백 모듈.
현재는 스텁(stub) 구현이며, 실제 API 키 설정 시 활성화됨.

지원 LLM:
- Claude API (Anthropic)
- OpenAI API (선택)
"""

import os
from src.utils import load_text

# 환경변수에서 API 키 로드
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_ENABLED = bool(ANTHROPIC_API_KEY)


def is_llm_available() -> bool:
    """LLM 폴백이 사용 가능한지 확인한다."""
    return LLM_ENABLED


def generate_llm_response(query: str, system_prompt: str = "") -> str | None:
    """LLM을 사용하여 답변을 생성한다.

    Args:
        query: 사용자 질문
        system_prompt: 시스템 프롬프트 (없으면 기본값 사용)

    Returns:
        LLM 답변 문자열 또는 None (API 키 미설정/오류 시)
    """
    if not LLM_ENABLED:
        return None

    if not system_prompt:
        try:
            system_prompt = load_text("config/system_prompt.txt")
        except Exception:
            system_prompt = "보세전시장 민원응대 전문 챗봇입니다."

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": query}],
        )
        return message.content[0].text
    except ImportError:
        return None
    except Exception:
        return None


def generate_llm_response_with_disclaimer(query: str) -> str:
    """LLM 답변에 면책 문구를 자동 추가한다."""
    response = generate_llm_response(query)
    if response is None:
        return ""

    disclaimer = (
        "\n\n안내:\n"
        "- 본 답변은 AI가 생성한 일반적인 안내용 설명이며, 구체적인 사실관계에 따라 달라질 수 있습니다.\n"
        "- 최종 처리는 관할 세관 또는 해당 소관기관 확인이 필요합니다."
    )
    return response + disclaimer
