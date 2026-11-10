#!/usr/bin/env bash
# G1 + risk escalation guard. Run from repo root before commit or at "done".
#
#   ./delivery/scripts/guard.sh
#   ./delivery/scripts/guard.sh --issue 12
#   ./delivery/scripts/guard.sh --staged
#   ./delivery/scripts/guard.sh --issue 12 --degrade --reason "Orca yok"
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
DEGRADE=false
REASON=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue) ISSUE="$2"; shift 2 ;;
    --staged) STAGED=true; shift ;;
    --degrade) DEGRADE=true; shift ;;
    --reason) REASON="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,8p' "$0"
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

# Capability path allowlist: seal yüzeylerinin glob'ları dışındaki yazım G1 ihlali.
# Seal yoksa veya allowlist çözülemezse davranış bugünkü gibi kalır (uyarı ile).
SCOPE_FILES=()
SCOPE_SURFACES=""
SCOPE_GLOBS=""
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
if [[ -n "$ISSUE" ]]; then
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
  printf '%s\n' "$CHANGED" > "$TMP_DIR/changed.txt"
  if [[ -n "$REPO" ]] && gh issue view "$ISSUE" --repo "$REPO" --json body -q .body \
    > "$TMP_DIR/body.md" 2>/dev/null && [[ -s "$TMP_DIR/body.md" ]]; then
    SCOPE_REPORT="$(python3 - "$TMP_DIR/body.md" "$TMP_DIR/changed.txt" \
      "${KIT_ROOT}/delivery/capabilities/registry.yaml" <<'PY'
import re
import sys

import yaml

body_path, changed_path, registry_path = sys.argv[1:4]
body = open(body_path, encoding="utf-8").read()
match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
seal = yaml.safe_load(match.group(1)) if match else {}
seal = seal if isinstance(seal, dict) else {}
surfaces = [str(item) for item in seal.get("surfaces") or []]
if not surfaces:
    print("SKIP|seal yüzey bildirmiyor")
    raise SystemExit
try:
    registry = yaml.safe_load(open(registry_path, encoding="utf-8")) or {}
except OSError:
    print("WARN|capability registry okunamadı, allowlist uygulanmadı")
    raise SystemExit

table = registry.get("surfaces") or {}
capabilities = registry.get("capabilities") or {}
scopes = []
for surface in surfaces:
    found = [
        (surface, str(glob))
        for glob in (table.get(surface) or {}).get("paths") or []
    ]
    for cap in capabilities.values():
        if surface in ((cap.get("match") or {}).get("surfaces") or []):
            found += [(surface, str(glob)) for glob in cap.get("paths") or []]
    if not found:
        print(f"WARN|registry'de tanımsız surface '{surface}', allowlist uygulanmadı")
    scopes += found
if not scopes:
    print("SKIP|allowlist çözülemedi, davranış bugünkü gibi")
    raise SystemExit
scopes += [("common", str(glob)) for glob in registry.get("common_paths") or []]


def to_regex(glob):
    out, index = ["^"], 0
    while index < len(glob):
        if glob.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        char = glob[index]
        out.append(
            "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
        )
        index += 1
    out.append("$")
    return re.compile("".join(out))


compiled = [(surface, glob, to_regex(glob)) for surface, glob in scopes]
names = ", ".join(dict.fromkeys(s for s, _ in scopes if s != "common"))
globs = ", ".join(dict.fromkeys(glob for _, glob in scopes))
blocked = [
    file
    for file in (line.strip() for line in open(changed_path, encoding="utf-8"))
    if file and not any(pattern.match(file) for _, _, pattern in compiled)
]
for file in blocked:
    print(f"BLOCK|{file}|{names}|{globs}")
if not blocked:
    print(f"SCOPE|{names}|{globs}")
PY
)" || SCOPE_REPORT="WARN|capability allowlist hesaplanamadı"
    while IFS='|' read -r kind one two three; do
      case "$kind" in
        WARN) echo "guard: uyarı — $one" >&2 ;;
        BLOCK) SCOPE_FILES+=("$one"); SCOPE_SURFACES="$two"; SCOPE_GLOBS="$three" ;;
      esac
    done <<< "$SCOPE_REPORT"
  else
    echo "guard: uyarı — seal gövdesi okunamadı, capability allowlist uygulanmadı" >&2
  fi
fi

if ! $NEED_ISSUE && [[ ${#SCOPE_FILES[@]} -eq 0 ]]; then
  echo "guard: OK (uygulama yolu, risk glob'u ve capability kapsamı değişmedi)"
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

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
if ! gh issue view "$ISSUE" --repo "$REPO" --json body -q .body \
  > "$TMP_DIR/body.md" 2>/dev/null; then
  echo "guard: BLOCKED — seal gövdesi okunamadı (fail-closed)" >&2
  exit 1
fi
if [[ ! -s "$TMP_DIR/body.md" ]]; then
  echo "guard: BLOCKED — seal gövdesi boş (fail-closed)" >&2
  exit 1
fi
if ! gh api "repos/${REPO}/issues/${ISSUE}/comments?per_page=100" --paginate \
  > "$TMP_DIR/comments.json" 2>/dev/null; then
  echo "guard: BLOCKED — onay yorumları okunamadı (fail-closed)" >&2
  exit 1
fi
if [[ ! -s "$TMP_DIR/comments.json" ]]; then
  echo "guard: BLOCKED — onay yorumları okunamadı (fail-closed)" >&2
  exit 1
fi

if ! python3 "${KIT_ROOT}/delivery/scripts/approvals.py" check-binding \
  --issue "$ISSUE" --root "$ROOT" --quiet \
  --body-file "$TMP_DIR/body.md" --comments-file "$TMP_DIR/comments.json"; then
  echo "guard: BLOCKED — onay digest'i uyuşmuyor (#${ISSUE})" >&2
  echo "  Onaydan sonra seal gövdesi değişti veya taban commit HEAD'in atası değil." >&2
  echo "  Yeniden onay al (demir-kit-accept + binding_sha256 + binding_base)." >&2
  exit 1
fi

RISK="$(python3 -c '
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
' < "$TMP_DIR/body.md")"

if [[ "$RISK_REQUIRED" == "critical" && "$RISK" != "high" && "$RISK" != "critical" ]]; then
  echo "guard: BLOCKED — registry critical glob'u, seal riski '${RISK:-yok}'" >&2
  echo "  Seal'de risk seviyesini yükselt (registry.yaml risk.auto_escalate)." >&2
  exit 1
fi
if [[ "$RISK_REQUIRED" == "high" && "$RISK" != "high" && "$RISK" != "critical" ]]; then
  echo "guard: BLOCKED — registry high glob'u, seal '${RISK:-yok}'" >&2
  exit 1
fi

if [[ ${#SCOPE_FILES[@]} -gt 0 ]]; then
  echo "guard: BLOCKED — capability dışı yazım (G1), yüzey allowlist'i dışında:" >&2
  printf '  %s\n' "${SCOPE_FILES[@]}" >&2
  echo "  yüzey: ${SCOPE_SURFACES}" >&2
  echo "  izinli glob'lar: ${SCOPE_GLOBS}" >&2
  echo "  Kapsamı daralt veya delivery/capabilities/registry.yaml içine glob ekle." >&2
  exit 1
fi

if $DEGRADE; then
  if [[ -z "$REASON" ]]; then
    echo "guard: BLOCKED — --degrade için --reason \"...\" gerekli" >&2
    exit 1
  fi
  python3 "${KIT_ROOT}/delivery/scripts/orca_gate.py" --project "$ROOT" \
    degrade --issue "$ISSUE" --reason "$REASON"
  echo "guard: OK — #${ISSUE} degrade kaydı yazıldı"
  exit 0
fi

if ! python3 "${KIT_ROOT}/delivery/scripts/orca_gate.py" --project "$ROOT" check --issue "$ISSUE"; then
  echo "guard: BLOCKED — epic worktree/orchestration kapısı geçmedi" >&2
  echo "  Epic worktree: python3 ${KIT_ROOT}/delivery/scripts/epic_worktree.py --project \"$ROOT\" ensure --epic <N>" >&2
  echo "  Gerçekten Orca yoksa: --degrade --reason \"...\"" >&2
  exit 1
fi

echo "guard: OK — #${ISSUE} agent-approved, risk '${RISK:-belirtilmemiş}', epic worktree"
