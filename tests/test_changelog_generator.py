"""Tests for src/changelog_generator.py — git-log → Markdown changelog."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import changelog_generator as cg


def test_parse_commit_recognizes_feat_prefix():
    c = cg.parse_commit("abc1234567", "feat: add streaming support")
    assert c.section == "Features"
    assert c.title == "add streaming support"
    assert c.short_sha == "abc1234"


def test_parse_commit_recognizes_fix_with_scope():
    c = cg.parse_commit("def4567890", "fix(auth): allow trailing slash")
    assert c.section == "Bug Fixes"
    assert c.title == "allow trailing slash"


def test_parse_commit_recognizes_breaking_change_marker():
    c = cg.parse_commit("aaa1111222", "feat!: breaking change")
    # `!` 는 prefix 매처에서 허용됨
    assert c.section == "Features"


def test_parse_commit_unknown_prefix_goes_to_other():
    c = cg.parse_commit("ccc3333444", "wip: hacking")
    assert c.section == "Other"
    # full message preserved
    assert "wip: hacking" in c.title


def test_parse_commit_no_prefix_goes_to_other():
    c = cg.parse_commit("eee5555666", "just a commit")
    assert c.section == "Other"
    assert c.title == "just a commit"


def test_collect_commits_returns_empty_when_git_missing():
    with patch("src.changelog_generator._run_git", side_effect=FileNotFoundError):
        result = cg.collect_commits("v0", "v1")
    assert result == []


def test_collect_commits_returns_empty_on_calledprocesserror():
    import subprocess
    with patch(
        "src.changelog_generator._run_git",
        side_effect=subprocess.CalledProcessError(128, "git"),
    ):
        result = cg.collect_commits("v0", "v1")
    assert result == []


def test_collect_commits_parses_log_lines():
    fake_log = (
        "abc1234567 feat: A\n"
        "def4567890 fix: B\n"
        "ghi7890123 chore: C\n"
    )
    with patch("src.changelog_generator._run_git", return_value=fake_log):
        commits = cg.collect_commits("v0", "v1")
    assert [c.short_sha for c in commits] == ["abc1234", "def4567", "ghi7890"]
    assert {c.section for c in commits} == {"Features", "Bug Fixes", "Chore"}


def test_group_by_section_orders_by_section_map():
    commits = [
        cg.parse_commit("a" * 7, "chore: x"),
        cg.parse_commit("b" * 7, "feat: y"),
        cg.parse_commit("c" * 7, "fix: z"),
    ]
    grouped = cg.group_by_section(commits)
    keys = list(grouped.keys())
    # feat → fix → chore
    assert keys.index("Features") < keys.index("Bug Fixes")
    assert keys.index("Bug Fixes") < keys.index("Chore")


def test_group_by_section_drops_empty_sections():
    commits = [cg.parse_commit("a" * 7, "feat: only")]
    grouped = cg.group_by_section(commits)
    assert list(grouped.keys()) == ["Features"]


def test_render_markdown_with_no_commits():
    out = cg.render_markdown([], title="Release v1")
    assert "Release v1" in out
    assert "변경 사항 없음" in out


def test_render_markdown_includes_section_headers_and_bullets():
    commits = [
        cg.parse_commit("a" * 40, "feat: add X"),
        cg.parse_commit("b" * 40, "fix: bug Y"),
    ]
    out = cg.render_markdown(commits, title="v2", from_ref="v1", to_ref="v2")
    assert "# v2 (v1 → v2)" in out
    assert "## ✨ Features" in out
    assert "- add X (`aaaaaaa`)" in out
    assert "## 🐛 Bug Fixes" in out
    assert "- bug Y (`bbbbbbb`)" in out


def test_generate_end_to_end_with_mocked_git():
    fake_log = "abc1234567 feat: A\ndef4567890 fix: B\n"
    with patch("src.changelog_generator._run_git", return_value=fake_log):
        out = cg.generate("v0", "HEAD", title="Release")
    assert "## ✨ Features" in out
    assert "- A (`abc1234`)" in out
    assert "- B (`def4567`)" in out


def test_generate_handles_blank_lines_in_log():
    fake_log = "abc1234567 feat: A\n\n\ndef4567890 fix: B\n"
    with patch("src.changelog_generator._run_git", return_value=fake_log):
        commits = cg.collect_commits("v0", "HEAD")
    assert len(commits) == 2
