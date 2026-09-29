#!/usr/bin/env bash
# Scaffold ecosystem.yaml and doc folders. Run from product repo root after kit-envision.
# Usage: ./vendor/demir-kit/tools/kit-init.sh --repo owner/name --profile web-product
set -euo pipefail

REPO=""
PROFILE=""
KIT_ROOT="${KIT_ROOT:-vendor/demir-kit}"
ECOSYSTEM_NAME="my-ecosystem"
WAIVE_ENVISION=0
BRIEF="docs/product/discovery-brief.md"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --name) ECOSYSTEM_NAME="$2"; shift 2 ;;
    --kit-root) KIT_ROOT="$2"; shift 2 ;;
    --waive-envision) WAIVE_ENVISION=1; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ ! -f kit.config.yaml ]]; then
  echo "kit-init: run kit-setup.sh first"
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(grep -E '^\s+repo:' kit.config.yaml | head -1 | sed 's/.*repo: *//')"
fi

if [[ -z "$PROFILE" ]]; then
  PROFILE="$(grep -E '^\s+default_profile:' kit.config.yaml | head -1 | sed 's/.*default_profile: *//' | tr -d '"')"
  PROFILE="${PROFILE:-web-product}"
fi

brief_envision_approved() {
  local brief="$1"
  [[ -f "$brief" ]] || return 1
  awk '
    BEGIN { in_fm=0; in_env=0 }
    /^---$/ { if (!seen++) { in_fm=1; next } else { in_fm=0; exit } }
    in_fm && /^envision:/ { in_env=1; next }
    in_fm && in_env && /^[^[:space:]]/ && !/^envision:/ { in_env=0 }
    in_fm && in_env && /^[[:space:]]+status:[[:space:]]+approved[[:space:]]*$/ { found=1 }
    END { exit(found ? 0 : 1) }
  ' "$brief"
}

if [[ "$WAIVE_ENVISION" -eq 0 ]]; then
  if [[ ! -f "$BRIEF" ]]; then
    echo "kit-init: missing $BRIEF — run kit-envision first or pass --waive-envision"
    exit 1
  fi
  if ! brief_envision_approved "$BRIEF"; then
    echo "kit-init: brief frontmatter envision.status must be approved — run kit-envision or --waive-envision"
    exit 1
  fi
fi

mkdir -p docs/product docs/architecture/decisions docs/design docs/agent scripts

for d in docs/product docs/architecture/decisions docs/design; do
  touch "$d/.gitkeep"
done

if [[ ! -f docs/agent/learnings.md ]]; then
  echo "# Learnings (one line + issue link per entry)" > docs/agent/learnings.md
fi

if [[ ! -f scripts/gate-behavior.sh ]]; then
  cp "$KIT_ROOT/templates/project/scripts/gate-behavior.sh" scripts/gate-behavior.sh
  chmod +x scripts/gate-behavior.sh
fi

extract_ecosystem_from_brief() {
  awk '
    /^## Proposed ecosystem/ { in_section=1; next }
    in_section && /^## / { exit }
    in_section && /^```yaml/ { in_yaml=1; next }
    in_yaml && /^```/ { exit }
    in_yaml { print }
  ' "$BRIEF"
}

materialize_layout_dirs() {
  local brief="$1"
  awk '
    /^## Proposed folder layout/ { in_section=1; next }
    in_section && /^## / { exit }
    in_section && /^```/ {
      if (!in_code) { in_code=1; next }
      exit
    }
    in_code {
      line=$0
      gsub(/^[[:space:]│├└─*]+/, "", line)
      gsub(/[[:space:]].*$/, "", line)
      if (line ~ /\.\./) next
      if (line ~ /^[a-zA-Z0-9_.@+-]+(\/[a-zA-Z0-9_.@+-]+)*\/?$/) print line
    }
  ' "$brief" | while IFS= read -r path; do
    path="${path%/}"
    [[ -z "$path" ]] && continue
    mkdir -p "$path"
  done
}

if [[ -f "$BRIEF" ]]; then
  materialize_layout_dirs "$BRIEF" 2>/dev/null || true
fi

if [[ ! -f ecosystem.yaml ]]; then
  EXTRACTED=""
  if [[ -f "$BRIEF" ]]; then
    EXTRACTED="$(extract_ecosystem_from_brief || true)"
  fi
  if [[ -n "$EXTRACTED" ]] && echo "$EXTRACTED" | grep -qE '^(name:|products:)'; then
    echo "$EXTRACTED" | sed -e "s|owner/repo|$REPO|g" > ecosystem.yaml
    echo "kit-init: ecosystem.yaml from discovery-brief § Proposed ecosystem"
  else
    sed -e "s|owner/repo|$REPO|g" \
        -e "s|name: my-ecosystem|name: $ECOSYSTEM_NAME|g" \
      "$KIT_ROOT/templates/ecosystem.yaml" > ecosystem.yaml
    echo "kit-init: template ecosystem.yaml (brief block missing or invalid — reconcile with agent)"
  fi
else
  echo "kit-init: ecosystem.yaml exists — skipped (reconcile with brief if needed)"
fi

echo "kit-init: profile hint $PROFILE (factory-routing may override from brief § Handoff)"
echo "Profile surfaces: see $KIT_ROOT/profiles/$PROFILE.yaml"
echo "Agent: promote MVO docs per $KIT_ROOT/references/envision-handoff.md"
echo "Next: scope-triage → factory-routing → work-package"
echo "Lifecycle: $KIT_ROOT/references/product-lifecycle.md"
