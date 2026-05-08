"""commit_lint - Conventional Commits validation (VV, cycle 13).

Single source of truth for commit message format checks.

Rules (default config):
  type(scope)!: subject

  - type:    one of feat/fix/perf/refactor/docs/test/ci/style/chore/build/revert
  - scope:   optional, must be lowercase identifier
  - !:       optional breaking-change marker
  - subject: required, <= 72 chars, no trailing period

Empty body is fine. Multi-line is fine; we only validate the first line.

External dependencies: none. ``lint_recent`` shells out to ``git log`` when a
binary is available, otherwise it returns an empty list (graceful degrade).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Iterable

DEFAULT_TYPES = (
    "feat",
    "fix",
    "perf",
    "refactor",
    "docs",
    "test",
    "ci",
    "style",
    "chore",
    "build",
    "revert",
)

# type(scope)!: subject  --  scope, !, ': ' all optional/positional
_HEADER_RE = re.compile(
    r"""
    ^
    (?P<type>[a-zA-Z]+)            # type word (validated separately)
    (?:\((?P<scope>[^)]*)\))?      # optional (scope)
    (?P<bang>!)?                   # optional breaking marker
    :\s+                           # ': ' separator
    (?P<subject>.+?)               # subject (non-greedy)
    \s*$
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class LintConfig:
    """Knobs for the linter. Defaults follow Conventional Commits 1.0."""

    allowed_types: tuple[str, ...] = DEFAULT_TYPES
    max_subject_len: int = 72
    min_subject_len: int = 3
    require_scope_for: tuple[str, ...] = ()
    allow_breaking: bool = True
    forbid_trailing_period: bool = True


@dataclass
class ParsedCommit:
    """Header parts. Any missing piece is ``None``; ``ok`` summarises parse."""

    raw: str
    type: str | None = None
    scope: str | None = None
    breaking: bool = False
    subject: str | None = None
    ok: bool = False


@dataclass
class Issue:
    code: str
    message: str
    severity: str = "error"  # 'error' or 'warning'

    def format(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


def parse_commit_message(message: str) -> ParsedCommit:
    """Parse the *first line* of a commit message. Never raises."""
    raw = (message or "").strip("\n")
    first_line = raw.split("\n", 1)[0] if raw else ""
    pc = ParsedCommit(raw=first_line)
    if not first_line:
        return pc
    m = _HEADER_RE.match(first_line)
    if not m:
        return pc
    pc.type = (m.group("type") or "").lower() or None
    scope = m.group("scope")
    pc.scope = scope.strip() if scope is not None else None
    pc.breaking = bool(m.group("bang"))
    pc.subject = (m.group("subject") or "").strip() or None
    pc.ok = bool(pc.type and pc.subject)
    return pc


def lint_commit(message: str, config: LintConfig | None = None) -> list[Issue]:
    """Return a list of issues for ``message``. Empty list = clean."""
    cfg = config or LintConfig()
    issues: list[Issue] = []

    if not message or not message.strip():
        issues.append(Issue("EMPTY", "commit message is empty"))
        return issues

    pc = parse_commit_message(message)
    if not pc.raw:
        issues.append(Issue("EMPTY", "commit message is empty"))
        return issues

    if not pc.ok or not pc.type:
        issues.append(
            Issue(
                "HEADER_FORMAT",
                "header does not match 'type(scope)!: subject' format",
            )
        )
        # If the type itself is recognisable, we still validate further.
        if pc.type is None:
            return issues

    if pc.type and pc.type not in cfg.allowed_types:
        issues.append(
            Issue(
                "TYPE_UNKNOWN",
                f"unknown type '{pc.type}' (allowed: {', '.join(cfg.allowed_types)})",
            )
        )

    if pc.scope is not None:
        if not pc.scope:
            issues.append(Issue("SCOPE_EMPTY", "scope parentheses are empty"))
        elif not re.fullmatch(r"[a-z0-9][a-z0-9\-/_.]*", pc.scope):
            issues.append(
                Issue(
                    "SCOPE_FORMAT",
                    f"scope '{pc.scope}' must be lowercase identifier",
                )
            )

    if cfg.require_scope_for and pc.type in cfg.require_scope_for and not pc.scope:
        issues.append(
            Issue(
                "SCOPE_REQUIRED",
                f"type '{pc.type}' requires a scope",
            )
        )

    if pc.breaking and not cfg.allow_breaking:
        issues.append(Issue("BREAKING_FORBIDDEN", "breaking-change marker '!' is disabled"))

    if pc.subject is not None:
        sub = pc.subject
        if len(sub) > cfg.max_subject_len:
            issues.append(
                Issue(
                    "SUBJECT_TOO_LONG",
                    f"subject is {len(sub)} chars (>{cfg.max_subject_len})",
                    severity="warning",
                )
            )
        if len(sub) < cfg.min_subject_len:
            issues.append(
                Issue(
                    "SUBJECT_TOO_SHORT",
                    f"subject is {len(sub)} chars (<{cfg.min_subject_len})",
                )
            )
        if cfg.forbid_trailing_period and sub.endswith("."):
            issues.append(
                Issue(
                    "SUBJECT_TRAILING_PERIOD",
                    "subject should not end with '.'",
                    severity="warning",
                )
            )
        if sub and sub[0].isupper() and pc.type in ("feat", "fix", "docs", "test"):
            issues.append(
                Issue(
                    "SUBJECT_CASE",
                    "subject should start lowercase",
                    severity="warning",
                )
            )

    return issues


@dataclass
class LintReport:
    messages: list[str] = field(default_factory=list)
    issues: list[list[Issue]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.messages)

    @property
    def clean(self) -> int:
        return sum(1 for ix in self.issues if not any(i.severity == "error" for i in ix))

    @property
    def errors(self) -> int:
        return sum(
            1 for ix in self.issues for i in ix if i.severity == "error"
        )

    @property
    def warnings(self) -> int:
        return sum(
            1 for ix in self.issues for i in ix if i.severity == "warning"
        )

    @property
    def ok(self) -> bool:
        return self.errors == 0


def lint_messages(
    messages: Iterable[str],
    config: LintConfig | None = None,
) -> LintReport:
    rep = LintReport()
    for msg in messages:
        rep.messages.append(msg)
        rep.issues.append(lint_commit(msg, config))
    return rep


def lint_recent(
    n: int = 10,
    repo_dir: str | None = None,
    config: LintConfig | None = None,
) -> LintReport:
    """Lint the last ``n`` commits from git. Empty report if git is missing."""
    rep = LintReport()
    if shutil.which("git") is None:
        return rep
    try:
        proc = subprocess.run(
            ["git", "log", f"-n{int(n)}", "--pretty=format:%s", "--no-merges"],
            cwd=repo_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return rep
    if proc.returncode != 0:
        return rep
    msgs = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return lint_messages(msgs, config)


def format_report(rep: LintReport) -> str:
    """Return a human-friendly summary of the report."""
    lines = [
        f"commits: {rep.total}  clean: {rep.clean}  errors: {rep.errors}  warnings: {rep.warnings}",
    ]
    for msg, issues in zip(rep.messages, rep.issues):
        if not issues:
            continue
        lines.append(f"- {msg!r}")
        for it in issues:
            lines.append(f"    {it.format()}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_TYPES",
    "LintConfig",
    "ParsedCommit",
    "Issue",
    "LintReport",
    "parse_commit_message",
    "lint_commit",
    "lint_messages",
    "lint_recent",
    "format_report",
]
