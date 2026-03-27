"""멀티턴 대화 세션 관리 모듈.

세션별 대화 기록, 미확인 항목, 컨텍스트를 관리한다.
"""

import time
import uuid
from dataclasses import dataclass, field


SESSION_TIMEOUT_SECONDS = 30 * 60  # 30분


@dataclass
class Session:
    """단일 대화 세션."""

    session_id: str
    history: list[dict] = field(default_factory=list)
    pending_confirmations: list[dict] = field(default_factory=list)
    confirmed: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def add_turn(self, query: str, answer: str) -> None:
        """대화 턴을 기록한다."""
        self.history.append({"query": query, "answer": answer})
        self.last_active = time.time()

    def set_pending_confirmations(self, confirmations: list[dict]) -> None:
        """확인 질문 목록을 설정한다."""
        self.pending_confirmations = list(confirmations)

    def process_confirmation_response(self, response: str) -> dict | None:
        """사용자의 확인 응답을 처리하고 다음 미확인 항목을 반환한다.

        긍정/부정 응답을 파싱하여 confirmed에 저장한다.
        다음 미확인 항목이 있으면 반환하고, 없으면 None을 반환한다.
        """
        if not self.pending_confirmations:
            return None

        current = self.pending_confirmations[0]
        is_positive = _is_positive_response(response)
        self.confirmed[current["question"]] = is_positive
        self.pending_confirmations.pop(0)
        self.last_active = time.time()

        if self.pending_confirmations:
            return self.pending_confirmations[0]
        return None

    def has_pending(self) -> bool:
        """미확인 항목이 있는지 확인한다."""
        return len(self.pending_confirmations) > 0

    def is_expired(self, now: float | None = None) -> bool:
        """세션 만료 여부를 확인한다."""
        if now is None:
            now = time.time()
        return (now - self.last_active) > SESSION_TIMEOUT_SECONDS

    def to_dict(self) -> dict:
        """세션 상태를 딕셔너리로 반환한다."""
        return {
            "session_id": self.session_id,
            "history": self.history,
            "pending_confirmations": self.pending_confirmations,
            "confirmed": self.confirmed,
            "context": self.context,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }


class SessionManager:
    """세션 생성, 조회, 삭제, 만료 관리."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        """새 세션을 생성한다."""
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """세션을 조회한다. 만료된 세션은 삭제 후 None을 반환한다."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            self.delete_session(session_id)
            return None
        return session

    def delete_session(self, session_id: str) -> bool:
        """세션을 삭제한다."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """만료된 세션을 모두 정리하고 삭제된 수를 반환한다."""
        now = time.time()
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if session.is_expired(now)
        ]
        for sid in expired_ids:
            del self._sessions[sid]
        return len(expired_ids)

    def active_count(self) -> int:
        """활성 세션 수를 반환한다."""
        return len(self._sessions)


def _is_positive_response(response: str) -> bool:
    """사용자 응답이 긍정인지 판단한다."""
    response_lower = response.strip().lower()
    positive_keywords = [
        "네", "예", "맞습니다", "맞아요", "그렇습니다", "맞아",
        "응", "넵", "ㅇㅇ", "yes", "y", "맞음", "그래요",
    ]
    negative_keywords = [
        "아니요", "아니오", "아닙니다", "아뇨", "아니",
        "no", "n", "ㄴㄴ", "아님", "아녜요",
    ]

    for kw in positive_keywords:
        if kw in response_lower:
            return True
    for kw in negative_keywords:
        if kw in response_lower:
            return False

    # 기본적으로 긍정으로 처리
    return True
