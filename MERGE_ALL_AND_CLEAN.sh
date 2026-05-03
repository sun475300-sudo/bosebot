#!/usr/bin/env bash
# bonded-chatbot — merge all 20 sandbox tracks → main, then clean up.
# Run from repo root: bash MERGE_ALL_AND_CLEAN.sh
set -uo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
ART="$REPO/outputs/pr-artifacts"
[ -f "$ART/PR_BODY_C.md" ] || ART="$REPO/../outputs/pr-artifacts"
[ -f "$ART/PR_BODY_C.md" ] || { echo "[ERR] PR artifacts not found"; exit 1; }
echo "Using artifacts at: $ART"

cd "$REPO"

# ── 0. sanity ──────────────────────────────────────────────────────────────
echo
echo "[0/5] gh CLI auth"
gh auth status >/dev/null 2>&1 || { echo "[ERR] run 'gh auth login' first"; exit 1; }

# ── branch table ───────────────────────────────────────────────────────────
declare -A B
B[D]=ci-bootstrap-202604280133
B[G]=small-fixes-202604280133
B[C]=fix-3-audits-202604280103
B[H]=perf-stability-cycle3-202604280151
B[J]=response-quality-202604280153
B[E]=h5-test-isolation-202604280135
B[F]=readme-ops-guide-202604280135
B[I]=observability-202604280152
B[K]=ops-automation-202604280154
B[L]=test-strengthen-202604280155
B[M]=privacy-202604280158
B[N]=backup-restore-202604280200
B[O]=per-user-rate-limit-202604280201
B[P]=ab-testing-202604280201
B[Q]=response-cache-202604280202
B[R]=audit-search-api-202604280604
B[S]=otel-tracing-202604280606
B[T]=lang-detection-202604280606
B[U]=anomaly-detection-202604280607
B[V]=static-analysis-hardening-202604280608

ORDER=(D G C H J E F I K L M N O P Q R S T U V)

# ── 1. sync main ───────────────────────────────────────────────────────────
echo
echo "[1/5] sync main"
[ -f .git/index.lock ] && rm -f .git/index.lock || true
git fetch origin
git checkout main && git pull --ff-only origin main

# ── 2. fetch + push ────────────────────────────────────────────────────────
echo
echo "[2/5] fetch bundles + push branches"
for L in "${ORDER[@]}"; do
  br="claude/${B[$L]}"
  echo "  --- $L  $br ---"
  if ! git rev-parse --verify "$br" >/dev/null 2>&1; then
    bundle="$ART/track-${L}_${B[$L]}.bundle"
    [ -f "$bundle" ] && git fetch "$bundle" "$br:$br" >/dev/null 2>&1 || true
  fi
  git push -u origin "$br" || echo "    push failed (may already be on remote)"
done

# ── 3. PR + auto-merge sequentially ────────────────────────────────────────
echo
echo "[3/5] create PR + auto-merge (squash → merge fallback)"
for L in "${ORDER[@]}"; do
  br="claude/${B[$L]}"
  body="$ART/PR_BODY_${L}.md"
  echo "  --- PR for $L : $br ---"
  gh pr create --base main --head "$br" --title "[$L] auto: $br" --body-file "$body" 2>/dev/null || true
  if ! gh pr merge "$br" --squash --delete-branch 2>/dev/null; then
    if ! gh pr merge "$br" --merge --delete-branch 2>/dev/null; then
      echo "    [WARN] $L merge failed — manual: gh pr view '$br'"
    fi
  fi
  git fetch origin >/dev/null 2>&1
  git pull --ff-only origin main >/dev/null 2>&1
done

# ── 4. local cleanup ───────────────────────────────────────────────────────
echo
echo "[4/5] local branch cleanup"
git checkout main
git pull --ff-only origin main
git remote prune origin
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/claude/); do
  echo "  deleting local $b"
  git branch -D "$b" >/dev/null 2>&1 || true
done

# ── 5. final state ─────────────────────────────────────────────────────────
echo
echo "[5/5] final state"
echo "--- last 5 commits on main ---"
git log --oneline -5
echo
echo "--- local branches ---"
git branch
echo
echo "--- still-open PRs ---"
gh pr list --state open
echo
echo "=== main HEAD ==="
git rev-parse HEAD
echo
echo "Done."
