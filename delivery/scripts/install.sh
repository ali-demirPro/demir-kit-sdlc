#!/usr/bin/env bash
# Install demir-kit runtime skills from the local working tree.
#
# Usage:
#   ./install.sh                 # v2 skills/ (local source)
#   ./install.sh --dry-run       # print source + skills, install nothing
#   ./install.sh --with-platform # + orchestration, orca-cli (global)
#   ./install.sh --capabilities  # + capability-scoped skills (skills.scoped)
#   ./install.sh --legacy        # same runtime set from the v1 archive
set -euo pipefail

CALLER_PWD="$PWD"
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
WITH_PLATFORM=false
LEGACY=false
DRY_RUN=false
CAPABILITIES=false

usage() {
  sed -n '2,8p' "$SCRIPT_PATH"
}

for arg in "$@"; do
  case "$arg" in
    --with-platform) WITH_PLATFORM=true ;;
    --capabilities) CAPABILITIES=true ;;
    --legacy) LEGACY=true ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) echo "install.sh: unknown argument: $arg" >&2; exit 1 ;;
  esac
done

REGISTRY_OUT="$(python3 - <<'PY'
import sys

try:
    import yaml
except ImportError:
    sys.exit("install.sh: PyYAML required (python3 -m pip install pyyaml)")

try:
    registry = yaml.safe_load(open("delivery/registry.yaml")) or {}
except FileNotFoundError:
    sys.exit("install.sh: delivery/registry.yaml not found")
except Exception as exc:  # noqa: BLE001
    sys.exit(f"install.sh: delivery/registry.yaml invalid — {exc}")

if not isinstance(registry, dict):
    sys.exit("install.sh: delivery/registry.yaml root must be a mapping")

skills = registry.get("skills") or {}
if not isinstance(skills, dict):
    sys.exit("install.sh: skills must be a mapping")
dir_value = skills.get("dir") or "skills"
if not isinstance(dir_value, str):
    sys.exit("install.sh: skills.dir must be a string")
runtime = skills.get("runtime") or []
if not isinstance(runtime, list) or not all(isinstance(name, str) for name in runtime):
    sys.exit("install.sh: skills.runtime must be a list of strings")
print(dir_value)
for name in runtime:
    print(name)
PY
)" || exit 1

SKILL_DIR_REL="$(head -n 1 <<< "$REGISTRY_OUT")"
SKILLS=()
while IFS= read -r skill; do
  [[ -n "$skill" ]] && SKILLS+=("$skill")
done < <(tail -n +2 <<< "$REGISTRY_OUT")

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  echo "install.sh: registry.skills.runtime is empty" >&2
  exit 1
fi

if [[ "$LEGACY" == true && "$CAPABILITIES" == true ]]; then
  echo "install.sh: --legacy ve --capabilities birlikte kullanılmaz (v1'de scoped skill yok)." >&2
  exit 1
fi

if [[ "$LEGACY" == true ]]; then
  SRC="file://${ROOT}/archive/v1.7"
  SKILL_ROOT="${ROOT}/archive/v1.7/skills"
  echo "WARNING: --legacy selected; installing the v1 archive from archive/v1.7/." >&2
else
  if [[ ! -e "$ROOT/.git" ]]; then
    echo "install.sh: ${ROOT} is not a git checkout root (no .git)." >&2
    echo "  Clone the kit or use --legacy. No GitHub fallback is attempted." >&2
    exit 1
  fi
  SRC="file://${ROOT}"
  SKILL_ROOT="${ROOT}/${SKILL_DIR_REL}"
fi

# `skills add` installs project-level skills into the working directory. Run it
# from the caller's checkout (a product or the kit itself) so a product never
# writes into the vendored kit. Falls back to the kit root when the caller is
# not a checkout.
INSTALL_DIR="$ROOT"
if [[ -f "${CALLER_PWD}/kit.config.yaml" ]]; then
  INSTALL_DIR="$CALLER_PWD"
fi

if [[ "$CAPABILITIES" == true ]]; then
  if ! SCOPED_SKILLS="$(python3 "${ROOT}/delivery/scripts/skill_scope.py" \
      --cwd "${CALLER_PWD}" --root "${ROOT}" --json \
      | python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin)["scoped"]))')"; then
    echo "install.sh: capability bildirimi okunamadı (.kit/capabilities.yaml)" >&2
    exit 1
  fi
  while IFS= read -r skill; do
    [[ -n "$skill" ]] && SKILLS+=("$skill")
  done <<< "$SCOPED_SKILLS"
fi

MISSING=()
for skill in "${SKILLS[@]}"; do
  [[ -f "${SKILL_ROOT}/${skill}/SKILL.md" ]] || MISSING+=("$skill")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "install.sh: missing skills under ${SKILL_ROOT}:" >&2
  printf '  - %s\n' "${MISSING[@]}" >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "install.sh: npx not found; install Node.js first." >&2
  exit 1
fi

if [[ "$WITH_PLATFORM" == true ]]; then
  PLATFORM_SKILLS=(orchestration orca-cli computer-use)
  if command -v orca >/dev/null 2>&1; then
    PLATFORM_ARGS=()
    for skill in "${PLATFORM_SKILLS[@]}"; do
      PLATFORM_ARGS+=(--skill "$skill")
    done
    if [[ "$DRY_RUN" == true ]]; then
      echo "[dry-run] orca skills install ${PLATFORM_ARGS[*]}"
    else
      echo "Installing Orca platform skills (version-matched) ..."
      orca skills install "${PLATFORM_ARGS[@]}"
    fi
  else
    echo "install.sh: orca CLI yok; npx fallback kullanılıyor (sürüm eşleşmesi garanti değil)." >&2
    for skill in "${PLATFORM_SKILLS[@]}"; do
      if [[ "$DRY_RUN" == true ]]; then
        echo "[dry-run] npx skills add https://github.com/stablyai/orca --skill ${skill} --global -y"
      else
        npx skills add https://github.com/stablyai/orca --skill "$skill" --global -y
      fi
    done
  fi
fi

echo "Skills source: ${SRC} (${#SKILLS[@]} skills)"
echo "Install dir: ${INSTALL_DIR}"
for skill in "${SKILLS[@]}"; do
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] (cd ${INSTALL_DIR}) npx skills add ${SRC} --skill ${skill} -y"
  else
    echo "Installing ${skill} ..."
    ( cd "$INSTALL_DIR" && npx skills add "$SRC" --skill "$skill" -y )
  fi
done

if [[ "$DRY_RUN" == true ]]; then
  echo "Dry run complete."
else
  echo "Done. Verify: orca skills installed"
fi
