# Track UU — CSV schema validator (stdlib only)

## What

- New `src/csv_validator.py`:
  - Declarative `Schema` + `ColumnRule` (type, required, length, regex,
    allowed list, unique, nullable).
  - `validate_csv(text, schema)` → `ValidationReport(ok, errors, ...)`.
  - Supported types: `str`, `int`, `float`, `bool`, `date` (ISO).
- New `scripts/validate_csv.py` — CLI runner (exit 0 OK / 1 fail / 2 script).
- New CI job `.github/workflows/csv-validate.yml` — gates `data/*.csv`
  changes on the matching schema in `config/csv_schemas/`.
- Sample schema `config/csv_schemas/faq.json` (no-op until a real CSV
  ships).

## Why

CSV uploads silently broke the FAQ pipeline twice. A tiny declarative
validator catches type drift and missing columns at PR review, with no
new dependency.

## Tests

`tests/test_csv_validator.py` — 7 tests:

- valid CSV passes
- missing required column flagged
- per-row type/regex/bool failures listed
- unique-column duplicate caught
- extra columns blocked when `allow_extra_columns=false`
- `min_rows` enforced
- schema JSON round-trip

```
tests/test_csv_validator.py .......                                      [100%]
7 passed in 0.27s
```

## Risk

- New module + CLI + opt-in workflow. Default builds unchanged.
- Workflow only fires when CSV/schema/validator paths change.

## Rollback

- `git revert <merge-sha>` — workflow + script + module + sample schema.
