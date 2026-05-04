"""Track UU — CSV schema validator (stdlib only).

A small declarative validator for ``data/*.csv`` uploads:

  - required columns (presence)
  - column types (``str``, ``int``, ``float``, ``bool``, ``date``)
  - per-column ``min_length``, ``max_length``, ``regex``, ``allowed``
  - ``unique`` columns
  - ``min_rows`` for the file as a whole

No PyYAML / pandas / pandera. Runs in CI and at upload-time.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


_TYPE_PARSERS = {
    "str":   lambda v: v,
    "int":   lambda v: int(v),
    "float": lambda v: float(v),
    "bool":  lambda v: _parse_bool(v),
    "date":  lambda v: _dt.date.fromisoformat(v),
}


def _parse_bool(v: str) -> bool:
    s = (v or "").strip().lower()
    if s in ("true", "1", "yes", "y", "t"):
        return True
    if s in ("false", "0", "no", "n", "f"):
        return False
    raise ValueError(f"not a bool: {v!r}")


@dataclass
class ColumnRule:
    name: str
    type: str = "str"
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    regex: Optional[str] = None
    allowed: Optional[Sequence[str]] = None
    unique: bool = False
    nullable: bool = False

    def __post_init__(self):
        if self.type not in _TYPE_PARSERS:
            raise ValueError(f"unknown type for {self.name!r}: {self.type}")
        self._regex = re.compile(self.regex) if self.regex else None

    def validate_value(self, raw: str) -> List[str]:
        errs: List[str] = []
        if raw is None or raw == "":
            if not self.nullable:
                errs.append(f"{self.name}: empty value")
            return errs
        # Type
        try:
            _TYPE_PARSERS[self.type](raw)
        except (ValueError, TypeError) as exc:
            errs.append(f"{self.name}: {exc}")
            return errs  # type failure short-circuits other checks
        # Length
        if self.min_length is not None and len(raw) < self.min_length:
            errs.append(f"{self.name}: length {len(raw)} < min {self.min_length}")
        if self.max_length is not None and len(raw) > self.max_length:
            errs.append(f"{self.name}: length {len(raw)} > max {self.max_length}")
        # Regex
        if self._regex and not self._regex.search(raw):
            errs.append(f"{self.name}: does not match /{self.regex}/")
        # Allowed
        if self.allowed is not None and raw not in self.allowed:
            errs.append(f"{self.name}: {raw!r} not in allowed list")
        return errs


@dataclass
class Schema:
    columns: List[ColumnRule]
    min_rows: int = 0
    allow_extra_columns: bool = True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Schema":
        cols = [ColumnRule(**c) for c in d.get("columns", [])]
        return cls(
            columns=cols,
            min_rows=int(d.get("min_rows", 0)),
            allow_extra_columns=bool(d.get("allow_extra_columns", True)),
        )

    @property
    def required_names(self) -> List[str]:
        return [c.name for c in self.columns if c.required]


@dataclass
class ValidationReport:
    ok: bool
    errors: List[str] = field(default_factory=list)
    rows_checked: int = 0
    columns: List[str] = field(default_factory=list)


def validate_csv(
    text_or_iter: Iterable[str] | str,
    schema: Schema,
    *,
    max_errors: int = 100,
) -> ValidationReport:
    """Validate a CSV string (or any iterable of lines)."""
    if isinstance(text_or_iter, str):
        source = io.StringIO(text_or_iter)
    else:
        source = io.StringIO("\n".join(text_or_iter))

    reader = csv.DictReader(source)
    cols = reader.fieldnames or []
    errors: List[str] = []

    # Header checks
    missing = [name for name in schema.required_names if name not in cols]
    if missing:
        errors.append(f"missing required columns: {missing}")
    if not schema.allow_extra_columns:
        rule_names = {c.name for c in schema.columns}
        extra = [c for c in cols if c not in rule_names]
        if extra:
            errors.append(f"unexpected extra columns: {extra}")

    rule_by_name = {c.name: c for c in schema.columns}
    seen_unique: Dict[str, set] = {n: set() for n, c in rule_by_name.items() if c.unique}
    rows_checked = 0
    for i, row in enumerate(reader, start=2):  # header is line 1
        rows_checked += 1
        for name, rule in rule_by_name.items():
            raw = row.get(name)
            value_errs = rule.validate_value(raw if raw is not None else "")
            for e in value_errs:
                errors.append(f"row {i}: {e}")
            if rule.unique and raw:
                if raw in seen_unique[name]:
                    errors.append(f"row {i}: {name}: duplicate value {raw!r}")
                else:
                    seen_unique[name].add(raw)
            if len(errors) >= max_errors:
                errors.append("(truncated; max_errors reached)")
                return ValidationReport(False, errors, rows_checked, cols)

    if rows_checked < schema.min_rows:
        errors.append(f"row count {rows_checked} < min_rows {schema.min_rows}")

    return ValidationReport(ok=not errors, errors=errors, rows_checked=rows_checked, columns=cols)


def load_schema_json(path: str) -> Schema:
    with open(path, "r", encoding="utf-8") as f:
        return Schema.from_dict(json.load(f))
