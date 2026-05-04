# Track TT — `/api/admin/quality/evaluate` (depends Track NN)

## What

- New `src/quality_evaluate.py`:
  - `evaluate(query, answer, model_path)` — pure function returning the
    7 raw feature values, the model's prediction (0..1), per-feature
    contribution, and the top-3 contributors.
  - `register_evaluate_routes(app, auth_required, model_path)` — mounts
    `POST /api/admin/quality/evaluate` behind whatever auth decorator the
    caller passes.
- Graceful degrade: if Track EE's `quality_model` isn't on the branch the
  module ships an inline mini-implementation so it still works.

## Wire-up (one line in web_server.py)

```python
from src.quality_evaluate import register_evaluate_routes
register_evaluate_routes(app, auth_required=admin_only)
```

## Why

NN surfaced the model summary; TT lets an admin paste a single
candidate response and see exactly why the model thinks it's good or
bad — useful for debugging FAQ wording without retraining.

## Tests

`tests/test_quality_evaluate.py` — 5 tests:

- evaluate returns 7 features + prediction in [0,1] + top contributors
- model loading honors `coefficients` from JSON
- endpoint 400 when `answer` missing
- endpoint returns JSON with required fields
- caller's `auth_required` decorator is applied

```
tests/test_quality_evaluate.py .....                                     [100%]
5 passed in 0.35s
```

## Risk

- Pure additive route + module. Default install unchanged.
- Auth is opt-in via injection — no implicit admin bypass.

## Rollback

- `git revert <merge-sha>` — single new module + test.
