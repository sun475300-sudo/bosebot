"""datetime 포맷팅 단일 헬퍼.

코드 곳곳에 흩어져 있던 ``strftime("%Y-%m-%d %H:%M:%S")`` 같은
ad-hoc 포맷팅을 통합한다. 표준 포맷 5종을 enum화하고,
한국어 친화 표시와 ISO 8601 표준 모두를 지원한다.

기본 시간대: ``UTC``. ``to_local()``로 KST 변환 가능.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

# 한국 표준시 (UTC+9)
KST = timezone(timedelta(hours=9), name="KST")
UTC = timezone.utc

# 표준 포맷 카탈로그
ISO_UTC = "iso_utc"           # 2026-05-04T10:23:45Z
ISO_LOCAL = "iso_local"       # 2026-05-04T19:23:45+09:00
DATE_KST = "date_kst"         # 2026-05-04
DATETIME_KST = "datetime_kst"  # 2026-05-04 19:23:45
DATETIME_KST_HUMAN = "datetime_kst_human"  # 2026년 05월 04일 19:23
COMPACT = "compact"           # 20260504_192345

_FORMATS = {
    ISO_UTC: ("%Y-%m-%dT%H:%M:%SZ", UTC),
    ISO_LOCAL: ("%Y-%m-%dT%H:%M:%S%z", KST),
    DATE_KST: ("%Y-%m-%d", KST),
    DATETIME_KST: ("%Y-%m-%d %H:%M:%S", KST),
    DATETIME_KST_HUMAN: ("%Y년 %m월 %d일 %H:%M", KST),
    COMPACT: ("%Y%m%d_%H%M%S", KST),
}


def _coerce(dt: Optional[Union[datetime, float, int]]) -> datetime:
    """입력값을 timezone-aware datetime으로 변환."""
    if dt is None:
        return datetime.now(tz=UTC)
    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt, tz=UTC)
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    raise TypeError(f"unsupported type for dt: {type(dt).__name__}")


def format(
    dt: Optional[Union[datetime, float, int]] = None,
    style: str = ISO_UTC,
) -> str:
    """주어진 시각을 표준 포맷으로 출력.

    Args:
        dt: ``datetime``, Unix timestamp(int/float), 또는 None(=now UTC).
        style: ``_FORMATS`` 키 중 하나.

    Returns:
        포맷팅된 문자열.
    """
    if style not in _FORMATS:
        raise ValueError(f"unknown style: {style}. valid: {sorted(_FORMATS)}")
    fmt, tz = _FORMATS[style]
    aware = _coerce(dt).astimezone(tz)
    return aware.strftime(fmt)


def now_iso() -> str:
    """현재 시각의 ISO 8601 UTC 문자열 (편의 wrapper)."""
    return format(None, ISO_UTC)


def to_kst(dt: Union[datetime, float, int]) -> datetime:
    """입력값을 KST timezone-aware datetime으로 반환."""
    return _coerce(dt).astimezone(KST)


def parse_iso(text: str) -> datetime:
    """ISO 8601 문자열 → timezone-aware datetime.

    ``Z`` 접미사를 ``+00:00``으로 변환해 ``fromisoformat``에 위임.
    """
    if not text or not isinstance(text, str):
        raise ValueError("non-empty string required")
    s = text.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def humanize_delta(seconds: float) -> str:
    """초 단위 시간차를 사람이 읽기 좋은 한국어로.

    예: 65 → "1분 5초", 3700 → "1시간 1분", 90061 → "1일 1시간".
    """
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds}초"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}분 {sec}초" if sec else f"{minutes}분"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}시간 {minutes}분" if minutes else f"{hours}시간"
    days, hours = divmod(hours, 24)
    return f"{days}일 {hours}시간" if hours else f"{days}일"


__all__ = [
    "KST",
    "UTC",
    "ISO_UTC",
    "ISO_LOCAL",
    "DATE_KST",
    "DATETIME_KST",
    "DATETIME_KST_HUMAN",
    "COMPACT",
    "format",
    "now_iso",
    "to_kst",
    "parse_iso",
    "humanize_delta",
]
