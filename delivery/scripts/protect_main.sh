#!/usr/bin/env bash
# Apply/check main branch protection: PR + delivery-doctor required.
set -euo pipefail
MODE="${1:---check}"
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
CONTEXT="${CONTEXT:-delivery-doctor}"
BRANCH="${BRANCH:-main}"

case "$MODE" in
  --apply)
    gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" --input - <<JSON
{
  "required_status_checks": {"strict": true, "contexts": ["${CONTEXT}"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
    echo "protect: applied ${BRANCH} PR + ${CONTEXT}"
    ;;
  --check)
    gh api "repos/${REPO}/branches/${BRANCH}/protection" | CONTEXT="$CONTEXT" python3 -c '
import json, os, sys
data = json.load(sys.stdin)
errors = []
contexts = ((data.get("required_status_checks") or {}).get("contexts") or [])
if os.environ["CONTEXT"] not in contexts:
    errors.append(f"required check eksik: {os.environ["CONTEXT"]}")
if (data.get("required_status_checks") or {}).get("strict") is not True:
    errors.append("strict check kapalı")
if (data.get("enforce_admins") or {}).get("enabled") is not True:
    errors.append("admin bypass açık")
if (data.get("allow_force_pushes") or {}).get("enabled") is not False:
    errors.append("force push açık")
if (data.get("allow_deletions") or {}).get("enabled") is not False:
    errors.append("deletion açık")
if not data.get("required_pull_request_reviews"):
    errors.append("PR zorunlu değil")
if errors:
    print("protect: " + "; ".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("protect: OK")
'
    echo "protect: OK ${BRANCH} PR + ${CONTEXT}"
    ;;
  *)
    echo "usage: protect_main.sh --apply|--check" >&2
    exit 2
    ;;
esac
