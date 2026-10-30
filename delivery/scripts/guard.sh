#!/usr/bin/env bash
# G1 + risk escalation guard. Run from repo root before commit or at "done".
#
#   ./delivery/scripts/guard.sh
#   ./delivery/scripts/guard.sh --issue 12
#   ./delivery/scripts/guard.sh --staged
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KIT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PRODUCT_ROOT="${PRODUCT_ROOT:-$(git -C "${PWD}" rev-parse --show-toplevel 2>/dev/null || pwd)}"
if [[ -f "${PRODUCT_ROOT}/kit.config.yaml" ]]; then
  ROOT="${PRODUCT_ROOT}"
else
  ROOT="${KIT_ROOT}"
fi
cd "$ROOT"

ISSUE=""
STAGED=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue) ISSUE="$2"; shift 2 ;;
    --staged) STAGED=true; shift ;;
    -h|--help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *) echo "guard.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
done

APP_PATHS=()
while IFS= read -r path; do
  [[ -n "$path" ]] && APP_PATHS+=("$path")
done < <(
  python3 - <<'PY'
import yaml
try:
    config = yaml.safe_load(open("kit.config.yaml")) or {}
except FileNotFoundError:
    config = {}
paths = (config.get("factory") or {}).get("app_paths")
if not paths:
    kit_root = str((config.get("kit") or {}).get("root", ""))
    paths = ["delivery", "skills"] if kit_root in (".", "") else ["src", "app", "lib"]
print("\n".join(paths))
PY
)

if $STAGED; then
  CHANGED="$(git diff --cached --name-only)"
else
  CHANGED="$(git diff --name-only HEAD 2>/dev/null || git diff --name-only)"
  CHANGED+=$'\n'"$(git ls-files --others --exclude-standard)"
fi
CHANGED="$(printf '%s\n' "$CHANGED" | sed '/^$/d' | sort -u)"
RISK_CHANGED="$(printf '%s\n' "$CHANGED" | python3 "${KIT_ROOT}/delivery/scripts/risk_filter.py" --registry "${KIT_ROOT}/delivery/registry.yaml" --project "${ROOT}")"

VIOLATIONS=()
for path in "${APP_PATHS[@]}"; do
  while IFS= read -r file; do
    [[ "$file" == "$path/"* ]] && VIOLATIONS+=("$file")
  done <<< "$CHANGED"
done

RISK_REQUIRED="$(printf '%s\n' "$RISK_CHANGED" | python3 "${KIT_ROOT}/delivery/scripts/risk_filter.py" --registry "${KIT_ROOT}/delivery/registry.yaml" --project "${ROOT}" --risk)"
NEED_ISSUE=false
if [[ ${#VIOLATIONS[@]} -gt 0 || "$RISK_REQUIRED" != "none" ]]; then
  NEED_ISSUE=true
fi
if ! $NEED_ISSUE; then
  echo "guard: OK (uygulama yolu ve risk glob'u değişmedi)"
  exit 0
fi

if [[ -z "$ISSUE" ]]; then
  if [[ ${#VIOLATIONS[@]} -gt 0 ]]; then
    echo "guard: BLOCKED — uygulama yolu değişti, issue yok:" >&2
    printf '  %s\n' "${VIOLATIONS[@]}" >&2
    echo "  Önce leaf mühürle (agent-approved), sonra --issue N ile tekrar çalıştır." >&2
  else
    echo "guard: BLOCKED — risk glob'u '${RISK_REQUIRED}', issue yok" >&2
    echo "  --issue N ile leaf riskini doğrula." >&2
  fi
  exit 1
fi

REPO="$(python3 - <<'PY'
import yaml
try:
    eco = yaml.safe_load(open("ecosystem.yaml")) or {}
    print((eco.get("tracker") or {}).get("repo", ""))
except FileNotFoundError:
    print("")
PY
)"
[[ -z "$REPO" ]] && REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
if [[ -z "$REPO" ]]; then
  echo "guard: BLOCKED — tracker.repo bulunamadı" >&2
  exit 1
fi

LABELS="$(gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name' 2>/dev/null || true)"
if ! grep -qx 'agent-approved' <<< "$LABELS"; then
  echo "guard: BLOCKED — issue #${ISSUE} agent-approved değil" >&2
  echo "  labels: $(tr '\n' ' ' <<< "$LABELS")" >&2
  exit 1
fi

RISK="$(gh issue view "$ISSUE" --repo "$REPO" --json body -q .body | python3 -c '
import re, sys, yaml
body = sys.stdin.read()
match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
if not match:
    print(""); raise SystemExit
try:
    data = yaml.safe_load(match.group(1)) or {}
    print((data.get("risk") or {}).get("level", ""))
except Exception:
    print("")
')"

if [[ "$RISK_REQUIRED" == "critical" && "$RISK" != "high" && "$RISK" != "critical" ]]; then
  echo "guard: BLOCKED — registry critical glob'u, seal riski '${RISK:-yok}'" >&2
  echo "  Seal'de risk seviyesini yükselt (registry.yaml risk.auto_escalate)." >&2
  exit 1
fi
if [[ "$RISK_REQUIRED" == "high" && "$RISK" != "high" && "$RISK" != "critical" ]]; then
  echo "guard: BLOCKED — registry high glob'u, seal '${RISK:-yok}'" >&2
  exit 1
fi

echo "guard: OK — #${ISSUE} agent-approved, risk '${RISK:-belirtilmemiş}'"
