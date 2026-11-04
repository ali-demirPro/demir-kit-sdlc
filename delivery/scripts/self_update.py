#!/usr/bin/env python3
"""Update a project's demir-kit from upstream with one command.

Varsayılan mod plan üretir (dry-run), ağa çıkmaz. `--apply` adımları sırayla
çalıştırır ve ilk hatada durur.

İki mod:
- `self`: kit kökü projenin kendisi (bu repo) — `git pull --ff-only` + `doctor`.
- `vendored`: kit proje içinde kopya — önbellekten `vendor_sync`, isteğe bağlı
  skill kurulumu, `doctor --product`.

Sözleşme alanları: `ok`, `project`, `kit_root`, `mode`, `version`, `upstream`,
`steps[]` (`{name, command}`); komutlar argv listesidir, shell yoktur.

Plan hatası (`ok:false`): `kit.upstream.git` yoksa (vendored ve `--source`
verilmemişse), desteklenmeyen biçimdeyse (`https://`, `http://`, `git@`,
`ssh://`, `file://`, `/` dışında) ya da `-` ile başlıyorsa; önbellek dizini
varsa ama git deposu değilse.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

CONFIG_NAME = "kit.config.yaml"
DEFAULT_REF = "main"
DEFAULT_CACHE = Path.home() / ".cache" / "demir-kit" / "upstream"
DOCTOR = Path("delivery") / "scripts" / "doctor.sh"
VENDOR_SYNC = Path("delivery") / "scripts" / "vendor_sync.py"
UPSTREAM_PREFIXES = ("https://", "http://", "git@", "ssh://", "file://", "/")


def find_project(start: Path) -> Path:
    """`kit.config.yaml` dosyasını yukarı doğru ara."""
    current = start.resolve()
    for path in (current, *current.parents):
        if (path / CONFIG_NAME).is_file():
            return path
    raise ValueError(f"{CONFIG_NAME} bulunamadı: {current}")


def load_config(project: Path) -> dict:
    path = project / CONFIG_NAME
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_NAME} kök mapping değil")
    kit = data.get("kit") or {}
    if not isinstance(kit, dict):
        raise ValueError(f"{CONFIG_NAME} kit bölümü mapping değil")
    return data


def kit_root(project: Path, config: dict) -> Path:
    root = (config.get("kit") or {}).get("root") or "."
    return (project / str(root)).resolve()


def validate_upstream(value: str) -> str:
    """`kit.upstream.git` biçimini doğrula; geçersizse net hata üret.

    Upstream argv'ye girer; `-` ile başlayan değer git seçeneği gibi
    yorumlanacağı için hiç kabul edilmez.
    """
    url = value.strip()
    if not url:
        raise ValueError(f"{CONFIG_NAME}: kit.upstream.git boş")
    if url.startswith("-"):
        raise ValueError(
            f"{CONFIG_NAME}: kit.upstream.git '-' ile başlayamaz: {url}"
        )
    if not any(url.startswith(prefix) for prefix in UPSTREAM_PREFIXES):
        raise ValueError(
            f"{CONFIG_NAME}: kit.upstream.git desteklenmeyen biçim: {url} "
            f"(beklenen: {', '.join(UPSTREAM_PREFIXES)})"
        )
    return url


def upstream_url(config: dict) -> str | None:
    upstream = (config.get("kit") or {}).get("upstream") or {}
    if not isinstance(upstream, dict):
        return None
    git = upstream.get("git")
    if not git:
        return None
    return validate_upstream(str(git))


def is_git_repo(path: Path) -> bool:
    """Dizin bir git deposu mu? (`.git` dizini ya da worktree dosyası)"""
    return (path / ".git").exists()


def origin_url(project: Path) -> str | None:
    """`git -C <proje> remote get-url origin`; yoksa ya da hata varsa None."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(project), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def same_repo(left: str | None, right: str | None) -> bool:
    """İki uzak adres aynı depoyu mu gösteriyor? (sondaki `/` ve `.git` yok sayılır)"""
    if not left or not right:
        return False

    def normalize(value: str) -> str:
        value = value.strip().rstrip("/")
        return value[:-4] if value.endswith(".git") else value

    return normalize(left) == normalize(right)


def read_version(root: Path) -> str | None:
    path = root / "VERSION"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def step(name: str, command: list[str]) -> dict:
    return {"name": name, "command": [str(part) for part in command]}


def build_plan(
    project: Path,
    source: Path | None = None,
    ref: str = DEFAULT_REF,
    skip_skills: bool = False,
    cache_dir: Path | None = None,
) -> dict:
    project = project.resolve()
    config = load_config(project)
    root = kit_root(project, config)
    upstream = upstream_url(config)
    # `self` yalnız kök projenin kendisi *ve* origin upstream ise; `kit.root: "."`
    # tek başına yetmez (`origin` başka depoysa kit vendored sayılır).
    mode = "vendored"
    if root == project and same_repo(origin_url(project), upstream):
        mode = "self"
    cache = Path(cache_dir).expanduser().resolve() if cache_dir else DEFAULT_CACHE
    steps: list[dict] = []

    if mode == "self":
        version = read_version(project)
        steps.append(step("pull", ["git", "-C", project, "pull", "--ff-only"]))
        steps.append(step("doctor", [project / DOCTOR]))
    else:
        local = Path(source).expanduser().resolve() if source else None
        if local is None:
            if not upstream:
                raise ValueError(f"{CONFIG_NAME}: kit.upstream.git yok")
            if cache.exists():
                if not is_git_repo(cache):
                    raise ValueError(f"önbellek bir git deposu değil: {cache}")
                steps.append(
                    step("fetch", ["git", "-C", cache, "fetch", "--depth", "1", "origin", ref])
                )
                steps.append(step("reset", ["git", "-C", cache, "reset", "--hard", "FETCH_HEAD"]))
            else:
                steps.append(
                    step(
                        "clone",
                        [
                            "git",
                            "clone",
                            "--depth",
                            "1",
                            "--branch",
                            ref,
                            "--",
                            upstream,
                            cache,
                        ],
                    )
                )
            local = cache
        version = read_version(local) or read_version(root)
        steps.append(
            step(
                "vendor_sync",
                [
                    sys.executable,
                    local / VENDOR_SYNC,
                    "--source",
                    local,
                    "--target",
                    project,
                    "--apply",
                ],
            )
        )
        if not skip_skills:
            steps.append(step("skills", ["bash", local / "install.sh"]))
        steps.append(step("doctor", [root / DOCTOR, "--product", "--root", project]))

    return {
        "ok": True,
        "project": str(project),
        "kit_root": str(root),
        "mode": mode,
        "version": version,
        "upstream": upstream,
        "steps": steps,
    }


def apply_plan(plan: dict) -> list[dict]:
    """Adımları sırayla çalıştır; ilk hatada dur."""
    results: list[dict] = []
    for item in plan["steps"]:
        completed = subprocess.run(
            item["command"],
            cwd=plan["project"],
            check=False,
        )
        results.append(
            {
                "name": item["name"],
                "command": item["command"],
                "exit_code": completed.returncode,
                "ok": completed.returncode == 0,
            }
        )
        if completed.returncode != 0:
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit güncelle")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="yalnız plan (varsayılan)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source", type=Path, help="yerel kit kökü")
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--skip-skills", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    if args.dry_run:
        args.apply = False

    try:
        project = find_project(args.project)
        plan = build_plan(
            project,
            source=args.source,
            ref=args.ref,
            skip_skills=args.skip_skills,
            cache_dir=args.cache_dir,
        )
    except (ValueError, OSError) as exc:
        if args.json:
            print(
                json.dumps(
                    {"ok": False, "error": str(exc)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        print(f"self_update: {exc}", file=sys.stderr)
        return 1

    results: list[dict] = []
    if args.apply:
        results = apply_plan(plan)
        plan["ok"] = all(item["ok"] for item in results)

    if args.json:
        payload = dict(plan)
        if args.apply:
            payload["steps"] = results
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"mode: {plan['mode']} · version: {plan['version'] or 'bilinmiyor'}")
        print(f"project: {plan['project']}")
        print(f"kit_root: {plan['kit_root']}")
        if plan["upstream"]:
            print(f"upstream: {plan['upstream']}")
        for item in plan["steps"] if not args.apply else results:
            command = " ".join(item["command"])
            if args.apply:
                mark = "ok" if item["ok"] else "fail"
                print(f"  {mark} {item['name']}: {command}")
            else:
                print(f"  {item['name']}: {command}")

    if args.apply and any(not item["ok"] for item in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
