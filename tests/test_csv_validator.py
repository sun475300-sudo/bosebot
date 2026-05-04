"""Tests for Track UU — CSV schema validator."""

from __future__ import annotations

import json

import pytest

from src.csv_validator import Schema, validate_csv


SCHEMA = Schema.from_dict({
    "min_rows": 1,
    "allow_extra_columns": False,
    "columns": [
        {"name": "id", "type": "int", "required": True, "unique": True},
        {"name": "question", "type": "str", "required": True, "min_length": 3, "max_length": 200},
        {"name": "category", "type": "str", "allowed": ["faq", "policy", "tax"]},
        {"name": "active", "type": "bool", "required": False, "nullable": True},
        {"name": "url", "type": "str", "regex": r"^https?://", "required": False, "nullable": True},
    ],
})


def test_valid_csv_passes():
    csv_text = (
        "id,question,category,active,url\n"
        "1,전시 신청 방법?,faq,true,https://x\n"
        "2,비용은 얼마?,faq,false,\n"
    )
    rep = validate_csv(csv_text, SCHEMA)
    assert rep.ok is True
    assert rep.errors == []
    assert rep.rows_checked == 2


def test_missing_required_column_flagged():
    csv_text = "id,question\n1,Hello\n"
    rep = validate_csv(csv_text, SCHEMA)
    assert rep.ok is False
    assert any("missing required columns" in e for e in rep.errors)


def test_type_violations_listed_per_row():
    csv_text = (
        "id,question,category,active,url\n"
        "abc,short?,faq,true,\n"             # id not int
        "2,QQ,faq,maybe,not-a-url\n"          # question too short, bool fail, url fail
    )
    rep = validate_csv(csv_text, SCHEMA)
    assert rep.ok is False
    msgs = " ".join(rep.errors)
    assert "id:" in msgs
    assert "active:" in msgs
    assert "url:" in msgs


def test_unique_constraint_catches_dup():
    csv_text = (
        "id,question,category,active,url\n"
        "1,One question?,faq,true,\n"
        "1,Two question?,policy,true,\n"
    )
    rep = validate_csv(csv_text, SCHEMA)
    assert rep.ok is False
    assert any("duplicate value" in e for e in rep.errors)


def test_extra_columns_blocked_when_disallowed():
    csv_text = (
        "id,question,category,active,url,unexpected\n"
        "1,Question text,faq,true,,xx\n"
    )
    rep = validate_csv(csv_text, SCHEMA)
    assert rep.ok is False
    assert any("unexpected extra columns" in e for e in rep.errors)


def test_min_rows_enforced():
    csv_text = "id,question,category,active,url\n"
    rep = validate_csv(csv_text, SCHEMA)
    assert rep.ok is False
    assert any("min_rows" in e for e in rep.errors)


def test_schema_from_json_roundtrip(tmp_path):
    p = tmp_path / "schema.json"
    p.write_text(json.dumps({
        "min_rows": 0,
        "columns": [{"name": "x", "type": "int", "required": True}],
    }), encoding="utf-8")
    from src.csv_validator import load_schema_json
    s = load_schema_json(str(p))
    assert s.required_names == ["x"]
