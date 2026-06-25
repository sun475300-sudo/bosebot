"""git log 기반 changelog 생성 모듈.

두 git ref(태그·브랜치·SHA) 사이의 커밋들을 분류해
Markdown 형식 changelog를 생성한다.

Conventional Commits 스타일 prefix를 인식한다::

    feat:     ✨ 새 기능
    fix:      🐛 버그 수정
    docs:     📝 문서
    style:    💄 코드 스타일
    refactor: ♻️  리팩토링
    perf:     ⚡ 성능
    test:     ✅ 테스트
    chore:    🔧 기타
    ci:       👷 CI/CD

prefix가 없는 커밋은 "기타" 섹션으로 분류된다.

이 모듈은 git이 설치되어 있지 않거나 (subprocess.CalledProcessError)
ref가 존재하지 않을 때 graceful degrade 한다.
"""

from __future__ import annotations

import re
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Optional, Sequence


# (prefix → (display_section, emoji))
SECTION_MAP: "OrderedDict[str, tuple]" = OrderedDict([
    ("feat", ("Features", "✨")),
    ("fix", ("Bug Fixes", "🐛")),
    ("perf", ("Performance", "⚡")),
    ("refactor", ("Refactor", "♻️")),
    ("docs", ("Documentation", "📝")),
    ("test", ("Tests", "✅")),
    ("ci", ("CI/CD", "👷")),
    ("style", ("Style", "💄")),
    ("chore", ("Chore", "🔧")),
])
OTHER_SECTION = ("Other", "📦")

_COMMIT_RE = re.compile(
    r"^(?P<sha>[0-9a-f]{7,40})\s+(?P<msg>.+?)$",
    re.MULTILINE,
)
_PREFIX_RE = re.compile(r"^(?P<type>[a-zA-Z]+)(\([^)]+\))?!?:\s*(?P<title>.+)$")


@dataclass
class Commit:
    """파싱된 커밋."""
    sha: str
    message: str
    section: str
    title: str
    emoji: str

    @property
    def short_sha(self) -> str:
        return self.sha[:7]


def parse_commit(sha: str, message: str) -> Commit:
    """커밋 메시지의 prefix를 분석해 섹션 분류."""
    m = _PREFIX_RE.match(message.strip())
    if m:
        prefix = m.group("type").lower()
        title = m.group("title").strip()
        if prefix in SECTION_MAP:
            section, emoji = SECTION_MAP[prefix]
        else:
            section, emoji = OTHER_SECTION
            title = message.strip()
    else:
        section, emoji = OTHER_SECTION
        title = message.strip()
    return Commit(sha=sha, message=message, section=section, title=title, emoji=emoji)


def _run_git(args: Sequence[str], repo_dir: Optional[str] = None) -> str:
    """git 명령 실행. 실패 시 CalledProcessError 그대로 raise."""
    cmd = ["git"]
    if repo_dir:
        cmd += ["-C", repo_dir]
    cmd += list(args)
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    return out


def collect_commits(
    from_ref: str,
    to_ref: str = "HEAD",
    repo_dir: Optional[str] = None,
) -> List[Commit]:
    """``from_ref..to_ref`` 사이의 커밋 목록.

    git이 없거나 ref가 없으면 빈 리스트를 반환한다 (graceful).
    """
    try:
        raw = _run_git(
            ["log", f"{from_ref}..{to_ref}", "--pretty=format:%H %s", "--no-merges"],
            repo_dir=repo_dir,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    commits = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, msg = line.partition(" ")
        if sha and msg:
            commits.append(parse_commit(sha, msg))
    return commits


def group_by_section(commits: Sequence[Commit]) -> "OrderedDict[str, List[Commit]]":
    """섹션 기준으로 정렬된 OrderedDict 반환."""
    # SECTION_MAP 순서대로 빈 리스트 생성 후 채운다
    grouped: "OrderedDict[str, List[Commit]]" = OrderedDict()
    for _, (section, _) in SECTION_MAP.items():
        grouped[section] = []
    grouped[OTHER_SECTION[0]] = []
    for c in commits:
        grouped[c.section].append(c)
    # 빈 섹션 제거
    return OrderedDict((k, v) for k, v in grouped.items() if v)


def render_markdown(
    commits: Sequence[Commit],
    title: str = "Changelog",
    from_ref: Optional[str] = None,
    to_ref: Optional[str] = None,
) -> str:
    """Markdown 문자열 생성.

    빈 commits → "변경 사항 없음" 안내.
    """
    lines: List[str] = []
    header = f"# {title}"
    if from_ref and to_ref:
        header += f" ({from_ref} → {to_ref})"
    lines.append(header)
    lines.append("")
    if not commits:
        lines.append("_변경 사항 없음._")
        return "\n".join(lines) + "\n"
    grouped = group_by_section(commits)
    for section, items in grouped.items():
        emoji = next((e for s, e in SECTION_MAP.values() if s == section), OTHER_SECTION[1])
        lines.append(f"## {emoji} {section}")
        lines.append("")
        for c in items:
            lines.append(f"- {c.title} (`{c.short_sha}`)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate(
    from_ref: str,
    to_ref: str = "HEAD",
    repo_dir: Optional[str] = None,
    title: str = "Changelog",
) -> str:
    """One-shot helper: collect + render."""
    commits = collect_commits(from_ref, to_ref, repo_dir=repo_dir)
    return render_markdown(commits, title=title, from_ref=from_ref, to_ref=to_ref)


__all__ = [
    "Commit",
    "SECTION_MAP",
    "parse_commit",
    "collect_commits",
    "group_by_section",
    "render_markdown",
    "generate",
]
