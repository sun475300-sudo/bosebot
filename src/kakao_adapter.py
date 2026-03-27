"""카카오톡 챗봇 스킬서버 어댑터.

카카오 i 오픈빌더의 스킬(Skill) 요청을 받아
보세전시장 챗봇 API로 변환하는 어댑터.

사용법:
    web_server.py에 블루프린트 등록하여 사용.
    카카오 오픈빌더 스킬 URL: http://서버주소:8080/kakao/chat
"""

from flask import Blueprint, request, jsonify

kakao_bp = Blueprint("kakao", __name__, url_prefix="/kakao")

# 카카오 오픈빌더 응답 포맷
def _build_kakao_response(text: str, quick_replies: list[dict] | None = None) -> dict:
    """카카오 i 오픈빌더 응답 JSON을 생성한다."""
    response = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text
                    }
                }
            ]
        }
    }

    if quick_replies:
        response["template"]["quickReplies"] = quick_replies

    return response


def _build_quick_replies(faq_suggestions: list[str]) -> list[dict]:
    """바로가기 버튼 목록을 생성한다."""
    return [
        {"messageText": q, "action": "message", "label": q[:20]}
        for q in faq_suggestions[:5]
    ]


def init_kakao_routes(chatbot, chat_logger=None):
    """카카오톡 라우트를 초기화한다.

    Args:
        chatbot: BondedExhibitionChatbot 인스턴스
        chat_logger: ChatLogger 인스턴스 (선택)
    """

    @kakao_bp.route("/chat", methods=["POST"])
    def kakao_chat():
        """카카오 오픈빌더 스킬 요청을 처리한다.

        카카오 요청 형식:
        {
            "intent": {"name": "..."},
            "userRequest": {
                "utterance": "사용자 질문",
                "user": {"id": "..."}
            }
        }
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify(_build_kakao_response("요청을 처리할 수 없습니다.")), 200

        user_request = data.get("userRequest", {})
        utterance = user_request.get("utterance", "").strip()

        if not utterance:
            return jsonify(_build_kakao_response(
                "질문을 입력해 주세요.\n\n"
                "예: 보세전시장이 무엇인가요?"
            )), 200

        # 챗봇 응답 생성
        answer = chatbot.process_query(utterance)

        # 로깅
        if chat_logger:
            try:
                from src.classifier import classify_query
                categories = classify_query(utterance)
                faq_match = chatbot.find_matching_faq(utterance, categories[0] if categories else "GENERAL")
                chat_logger.log_query(
                    query=utterance,
                    category=categories[0] if categories else "GENERAL",
                    faq_id=faq_match.get("id") if faq_match else None,
                    is_escalation=False,
                    response_preview=answer[:200],
                )
            except Exception:
                pass

        # 바로가기 버튼 추가
        quick_replies = _build_quick_replies([
            "보세전시장이란?",
            "물품 반입 절차",
            "현장 판매 가능?",
            "문의처 안내",
        ])

        return jsonify(_build_kakao_response(answer, quick_replies)), 200

    @kakao_bp.route("/welcome", methods=["POST"])
    def kakao_welcome():
        """카카오 오픈빌더 웰컴 블록 응답."""
        persona = chatbot.get_persona()
        quick_replies = _build_quick_replies([
            "보세전시장이란?",
            "물품 반입/반출",
            "현장 판매 가능?",
            "견본품 반출",
            "문의처 안내",
        ])
        return jsonify(_build_kakao_response(persona, quick_replies)), 200

    return kakao_bp
