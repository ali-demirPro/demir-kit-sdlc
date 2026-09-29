#!/usr/bin/env bash
# Sync vendored demir-kit from upstream. Run from product repo root.
# Usage: demir-kit/tools/kit-upgrade.sh [--from PATH] [--git URL] [--dry-run] [--no-delete] [--skip-orca]
set -euo pipefail

PRODUCT_ROOT="$(pwd)"
FROM=""
GIT_URL=""
DRY_RUN=false
NO_DELETE=false
SKIP_ORCA=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --git) GIT_URL="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --no-delete) NO_DELETE=true; shift ;;
    --skip-orca) SKIP_ORCA=true; shift ;;
    -h|--help)
      echo "Usage: kit-upgrade.sh [--from PATH] [--git URL] [--dry-run] [--no-delete] [--skip-orca]"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

CONFIG="${PRODUCT_ROOT}/kit.config.yaml"
if [[ ! -f "$CONFIG" ]]; then
  echo "kit-upgrade: kit.config.yaml not found — run from product repo root"
  exit 1
fi

yaml_val() {
  local key="$1"
  grep -E "^[[:space:]]*${key}:" "$CONFIG" 2>/dev/null | head -1 | sed -E 's/^[^:]*:[[:space:]]*//' | sed -E 's/[[:space:]]+#.*$//' | tr -d '"' | tr -d "'"
}

KIT_ROOT_REL="$(yaml_val 'root' || true)"
[[ -z "$KIT_ROOT_REL" ]] && KIT_ROOT_REL="demir-kit"
KIT_DEST="${PRODUCT_ROOT}/${KIT_ROOT_REL}"

OLD_VERSION=""
if [[ -f "${KIT_DEST}/VERSION" ]]; then
  OLD_VERSION="$(tr -d '[:space:]' < "${KIT_DEST}/VERSION")"
fi

UPSTREAM_LOCAL="$(yaml_val 'local' || true)"
if [[ -z "$UPSTREAM_LOCAL" ]]; then
  UPSTREAM_LOCAL="$(grep -A5 '^[[:space:]]*upstream:' "$CONFIG" 2>/dev/null | grep -E '^\s+local:' | head -1 | sed -E 's/^\s+local:\s*//' | sed -E 's/[[:space:]]+#.*$//' | tr -d '"' || true)"
fi
UPSTREAM_GIT="$(yaml_val 'git' || true)"
if [[ -z "$UPSTREAM_GIT" ]]; then
  UPSTREAM_GIT="$(grep -A5 '^[[:space:]]*upstream:' "$CONFIG" 2>/dev/null | grep -E '^\s+git:' | head -1 | sed -E 's/^\s+git:\s*//' | sed -E 's/[[:space:]]+#.*$//' | tr -d '"' || true)"
fi

OVERLAY_REL=""
if grep -q '^[[:space:]]*overlay:' "$CONFIG" 2>/dev/null; then
  OVERLAY_REL="$(yaml_val 'overlay' || true)"
fi

SOURCE=""
CLEANUP=""

resolve_source() {
  if [[ -n "$FROM" ]]; then
    SOURCE="$FROM"
    return
  fi
  if [[ -n "$UPSTREAM_LOCAL" ]]; then
    if [[ "$UPSTREAM_LOCAL" != /* ]]; then
      SOURCE="${PRODUCT_ROOT}/${UPSTREAM_LOCAL}"
    else
      SOURCE="$UPSTREAM_LOCAL"
    fi
    if [[ -d "$SOURCE/.git" ]] && command -v git >/dev/null 2>&1; then
      echo "kit-upgrade: pulling ${SOURCE} ..."
      git -C "$SOURCE" pull --ff-only || git -C "$SOURCE" pull
    fi
    return
  fi
  if [[ -n "$GIT_URL" ]]; then
    SOURCE="$(mktemp -d /tmp/demir-kit-upgrade.XXXXXX)"
    CLEANUP="$SOURCE"
    echo "kit-upgrade: cloning ${GIT_URL} ..."
    git clone --depth 1 "$GIT_URL" "$SOURCE"
    return
  fi
  if [[ -n "$UPSTREAM_GIT" ]]; then
    SOURCE="$(mktemp -d /tmp/demir-kit-upgrade.XXXXXX)"
    CLEANUP="$SOURCE"
    echo "kit-upgrade: cloning ${UPSTREAM_GIT} ..."
    git clone --depth 1 "$UPSTREAM_GIT" "$SOURCE"
    return
  fi
  echo "kit-upgrade: no source — set kit.upstream.local or kit.upstream.git in kit.config.yaml, or pass --from / --git"
  exit 1
}

resolve_source
SOURCE="$(cd "$SOURCE" && pwd)"

if [[ ! -f "${SOURCE}/VERSION" ]]; then
  echo "kit-upgrade: invalid kit source (missing VERSION): ${SOURCE}"
  [[ -n "$CLEANUP" ]] && rm -rf "$CLEANUP"
  exit 1
fi

NEW_VERSION="$(tr -d '[:space:]' < "${SOURCE}/VERSION")"

RSYNC_OPTS=(-a --exclude '.git' --exclude '.DS_Store')
[[ "$NO_DELETE" == false ]] && RSYNC_OPTS+=(--delete)
[[ "$DRY_RUN" == true ]] && RSYNC_OPTS+=(-n --verbose)

echo "kit-upgrade: ${SOURCE}/ → ${KIT_DEST}/"
if [[ -n "$OLD_VERSION" ]]; then
  echo "kit-upgrade: version ${OLD_VERSION} → ${NEW_VERSION}"
else
  echo "kit-upgrade: installing kit ${NEW_VERSION}"
fi

mkdir -p "$KIT_DEST"
rsync "${RSYNC_OPTS[@]}" "${SOURCE}/" "${KIT_DEST}/"

if [[ "$DRY_RUN" == false && -n "$OVERLAY_REL" ]]; then
  OVERLAY_PATH="${PRODUCT_ROOT}/${OVERLAY_REL}"
  if [[ -d "$OVERLAY_PATH" ]]; then
    echo "kit-upgrade: applying overlay ${OVERLAY_PATH}/"
    rsync -a "${OVERLAY_PATH}/" "${KIT_DEST}/"
  fi
fi

if [[ "$DRY_RUN" == false ]]; then
  if grep -q '^[[:space:]]*version:' "$CONFIG"; then
    if [[ "$(uname)" == Darwin ]]; then
      sed -i '' -E "s/^([[:space:]]*version:)[[:space:]]*.*/\\1 \"${NEW_VERSION}\"/" "$CONFIG"
    else
      sed -i -E "s/^([[:space:]]*version:)[[:space:]]*.*/\\1 \"${NEW_VERSION}\"/" "$CONFIG"
    fi
  fi

  if [[ "$SKIP_ORCA" == false && -x "${PRODUCT_ROOT}/scripts/install-orca-user-skills.sh" ]]; then
    echo "kit-upgrade: refreshing Orca owner skills ..."
    "${PRODUCT_ROOT}/scripts/install-orca-user-skills.sh" || true
  fi
fi

[[ -n "$CLEANUP" ]] && rm -rf "$CLEANUP"

if [[ "$DRY_RUN" == true ]]; then
  echo "kit-upgrade: dry-run complete (no changes written)"
else
  echo "kit-upgrade: done. kit.config.yaml version → ${NEW_VERSION}"
  if command -v git >/dev/null 2>&1 && git -C "$PRODUCT_ROOT" rev-parse --is-inside-work-tree &>/dev/null; then
    git -C "$PRODUCT_ROOT" diff --stat "${KIT_ROOT_REL}" "$CONFIG" 2>/dev/null || true
  fi
fi
