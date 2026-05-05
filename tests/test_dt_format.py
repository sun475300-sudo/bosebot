"""Tests for src/dt_format.py — single datetime formatting helper."""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import dt_format as dtf


# 고정 기준 시각: 2026-05-04T10:23:45Z
FIXED_UTC = datetime(2026, 5, 4, 10, 23, 45, tzinfo=timezone.utc)


def test_format_iso_utc_with_aware_input():
    assert dtf.format(FIXED_UTC, dtf.ISO_UTC) == "2026-05-04T10:23:45Z"


def test_format_iso_local_returns_kst_offset():
    out = dtf.format(FIXED_UTC, dtf.ISO_LOCAL)
    # KST = UTC+9 → 19:23:45+0900
    assert out.startswith("2026-05-04T19:23:45")
    assert "+0900" in out or "+09:00" in out


def test_format_date_kst_shifts_day_when_needed():
    # 2026-05-04 23:30 UTC → KST 2026-05-05 08:30 → date "2026-05-05"
    late = datetime(2026, 5, 4, 23, 30, 0, tzinfo=timezone.utc)
    assert dtf.format(late, dtf.DATE_KST) == "2026-05-05"


def test_format_datetime_kst_human():
    out = dtf.format(FIXED_UTC, dtf.DATETIME_KST_HUMAN)
    assert "2026년 05월 04일" in out
    assert "19:23" in out


def test_format_compact():
    assert dtf.format(FIXED_UTC, dtf.COMPACT) == "20260504_192345"


def test_format_accepts_unix_timestamp():
    ts = FIXED_UTC.timestamp()
    assert dtf.format(ts, dtf.ISO_UTC) == "2026-05-04T10:23:45Z"


def test_format_accepts_naive_datetime_as_utc():
    naive = datetime(2026, 5, 4, 10, 23, 45)  # no tz
    assert dtf.format(naive, dtf.ISO_UTC) == "2026-05-04T10:23:45Z"


def test_format_none_returns_now():
    out = dtf.format(None, dtf.ISO_UTC)
    assert out.endswith("Z")
    assert len(out) == 20  # "YYYY-MM-DDTHH:MM:SSZ"


def test_format_unknown_style_raises():
    with pytest.raises(ValueError, match="unknown style"):
        dtf.format(FIXED_UTC, "made_up_style")


def test_format_rejects_unsupported_type():
    with pytest.raises(TypeError):
        dtf.format(["nope"], dtf.ISO_UTC)


def test_now_iso_returns_z_suffix():
    out = dtf.now_iso()
    assert out.endswith("Z")


def test_to_kst_returns_kst_aware():
    kst = dtf.to_kst(FIXED_UTC)
    assert kst.utcoffset().total_seconds() == 9 * 3600
    assert kst.hour == 19


def test_parse_iso_with_z():
    dt = dtf.parse_iso("2026-05-04T10:23:45Z")
    assert dt == FIXED_UTC


def test_parse_iso_with_offset():
    dt = dtf.parse_iso("2026-05-04T19:23:45+09:00")
    assert dt.astimezone(timezone.utc) == FIXED_UTC


def test_parse_iso_naive_treated_utc():
    dt = dtf.parse_iso("2026-05-04T10:23:45")
    assert dt == FIXED_UTC


def test_humanize_delta_seconds_only():
    assert dtf.humanize_delta(45) == "45초"


def test_humanize_delta_minutes():
    assert dtf.humanize_delta(65) == "1분 5초"
    assert dtf.humanize_delta(120) == "2분"


def test_humanize_delta_hours():
    assert dtf.humanize_delta(3700) == "1시간 1분"
    assert dtf.humanize_delta(7200) == "2시간"


def test_humanize_delta_days():
    assert dtf.humanize_delta(90061) == "1일 1시간"
    assert dtf.humanize_delta(86400) == "1일"


def test_humanize_delta_negative_clamped():
    assert dtf.humanize_delta(-100) == "0초"
