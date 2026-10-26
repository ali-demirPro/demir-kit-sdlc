#!/usr/bin/env bash
# Resolve npx skills add source for demir-kit owner skills.
# Usage: source this file; resolve_skills_source "/path/to/product/repo"
# Prints: https://github.com/... or file:///path/with/.git
resolve_skills_source() {
  local product_root="${1:?product root required}"
  local config="${product_root}/kit.config.yaml"
  local kit_rel="demir-kit"
  local default_git="https://github.com/ali-demirPro/demir-kit-sdlc.git"

  if [[ -f "$config" ]]; then
    local r
    r="$(grep -E '^[[:space:]]*root:' "$config" | head -1 | sed -E 's/^[^:]*:[[:space:]]*//' | sed -E 's/[[:space:]]+#.*$//' | tr -d '"' | tr -d "'")"
    [[ -n "$r" ]] && kit_rel="$r"
  fi

  local vendor="${product_root}/${kit_rel}"
  local upstream_local=""
  local upstream_git=""

  if [[ -f "$config" ]]; then
    upstream_local="$(grep -E '^[[:space:]]+local:' "$config" | head -1 | sed -E 's/^[^:]*:[[:space:]]*//' | sed -E 's/[[:space:]]+#.*$//' | tr -d '"' | tr -d "'")"
    upstream_git="$(grep -E '^[[:space:]]+git:' "$config" | head -1 | sed -E 's/^[^:]*:[[:space:]]*//' | sed -E 's/[[:space:]]+#.*$//' | tr -d '"' | tr -d "'")"
  fi

  try_local_git() {
    local p="$1"
    [[ -z "$p" ]] && return 1
    if [[ "$p" != /* ]]; then
      p="${product_root}/${p}"
    fi
    p="$(cd "$p" 2>/dev/null && pwd)" || return 1
    if [[ -d "${p}/.git" ]]; then
      echo "file://${p}"
      return 0
    fi
    return 1
  }

  local resolved
  if resolved="$(try_local_git "$upstream_local")"; then
    echo "$resolved"
    return 0
  fi
  if [[ -d "${vendor}/.git" ]]; then
    echo "file://$(cd "$vendor" && pwd)"
    return 0
  fi
  if [[ -n "$upstream_git" ]]; then
    echo "$upstream_git"
    return 0
  fi
  echo "$default_git"
}
