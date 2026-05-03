#!/usr/bin/env bash
# bonded-chatbot — apply 3 fix patches + run new tests
set -euo pipefail
cd "$(dirname "$0")/.."

echo "── checking patches ──"
for p in patches/0001-session-auto-create.patch patches/0002-brute-force-lockout.patch patches/0003-rate-limit-env.patch; do
  git apply --check "$p" && echo "  [✓] $p"
done

echo ""
echo "── applying ──"
git apply patches/0001-session-auto-create.patch && echo "  [✓] 0001 session-auto-create"
git apply patches/0002-brute-force-lockout.patch && echo "  [✓] 0002 brute-force-lockout"
git apply patches/0003-rate-limit-env.patch       && echo "  [✓] 0003 rate-limit-env"

echo ""
echo "── running 13 new tests ──"
python3 -m pytest tests/test_session_auto_create.py tests/test_auth_lockout.py tests/test_rate_limit_env.py -v

echo ""
echo "── status ──"
git status --short
echo ""
echo "Done. Review:  git diff"
echo "Commit:        git add -A && git commit -m 'fix: apply 3 audit patches'"
