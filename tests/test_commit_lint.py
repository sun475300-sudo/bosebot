"""Tests for src.commit_lint (track VV)."""

from __future__ import annotations

from src.commit_lint import (
    LintConfig,
    format_report,
    lint_commit,
    lint_messages,
    lint_recent,
    parse_commit_message,
)


def _codes(issues):
    return [i.code for i in issues]


def test_parses_valid_conventional_commit():
    pc = parse_commit_message("feat(api): add hybrid search ranking")
    assert pc.ok is True
    assert pc.type == "feat"
    assert pc.scope == "api"
    assert pc.breaking is False
    assert pc.subject == "add hybrid search ranking"
    # No errors for a clean commit
    issues = lint_commit("feat(api): add hybrid search ranking")
    assert all(i.severity != "error" for i in issues)


def test_missing_type_or_separator_is_error():
    issues = lint_commit("just a free-form message")
    assert "HEADER_FORMAT" in _codes(issues)

    issues2 = lint_commit("nope:no space")  # missing space after ':'
    assert "HEADER_FORMAT" in _codes(issues2)

    # empty message
    issues3 = lint_commit("")
    assert "EMPTY" in _codes(issues3)


def test_subject_length_caps():
    too_long = "feat: " + ("x" * 80)  # 80-char subject, default max 72
    issues = lint_commit(too_long)
    assert "SUBJECT_TOO_LONG" in _codes(issues)
    # warning, not blocking error
    assert any(
        i.code == "SUBJECT_TOO_LONG" and i.severity == "warning" for i in issues
    )

    too_short = "feat: hi"  # 2 chars subject, default min 3 — len('hi')=2
    issues2 = lint_commit(too_short)
    assert "SUBJECT_TOO_SHORT" in _codes(issues2)


def test_breaking_change_marker_recognized():
    pc = parse_commit_message("refactor(core)!: drop python 3.8 support")
    assert pc.breaking is True
    issues = lint_commit("refactor(core)!: drop python 3.8 support")
    assert all(i.severity != "error" for i in issues)

    cfg = LintConfig(allow_breaking=False)
    issues2 = lint_commit("refactor(core)!: drop python 3.8 support", cfg)
    assert "BREAKING_FORBIDDEN" in _codes(issues2)


def test_unknown_type_and_scope_format_caught():
    issues = lint_commit("WIP(API): something")
    codes = _codes(issues)
    assert "TYPE_UNKNOWN" in codes
    assert "SCOPE_FORMAT" in codes


def test_lint_messages_aggregates_and_report_formats():
    rep = lint_messages(
        [
            "feat: add hybrid search",      # clean
            "WIP something",                  # error
            "fix: trim trailing whitespace.", # warning (trailing period)
        ]
    )
    assert rep.total == 3
    assert rep.errors >= 1
    assert rep.warnings >= 1
    text = format_report(rep)
    assert "commits: 3" in text
    assert "WIP something" in text


def test_lint_recent_graceful_without_repo(tmp_path, monkeypatch):
    # Force the git lookup to fail by pointing PATH at an empty dir.
    monkeypatch.setenv("PATH", str(tmp_path))
    rep = lint_recent(n=5, repo_dir=str(tmp_path))
    assert rep.total == 0
    assert rep.ok is True
