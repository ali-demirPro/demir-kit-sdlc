#!/usr/bin/env python3
"""Update a project's demir-kit from upstream with one command.

Varsayılan mod plan üretir (dry-run), ağa çıkmaz. `--apply` adımları sırayla
çalıştırır ve ilk hatada durur.

Üç mod (tespit sırası: `self` → `submodule` → `vendored`):
- `self`: kit kökü projenin kendisi (bu repo) — `git pull --ff-only` + `doctor`.
- `submodule`: kit kökü bir git submodule (`.git` ya da `.gitmodules` kaydı) —
  `git submodule update --init [--remote]`, isteğe bağlı `--ref` pinleme,
  config sürümü, `doctor --product`. Commit atılmaz; pointer ürün reposunda
  commit'lenir.
- `vendored`: kit proje içinde kopya — önbellekten `vendor_sync`, isteğe bağlı
  skill kurulumu, `doctor --product`.

Sözleşme alanları: `ok`, `project`, `kit_root`, `mode`, `version`, `upstream`,
`steps[]` (`{name, command}` ya da iç işlem `{name, internal}`); komutlar argv
listesidir, shell yoktur.

Plan hatası (`ok:false`): `kit.upstream.git` yoksa (vendored ve `--source`
verilmemişse), desteklenmeyen biçimdeyse (`https://`, `http://`, `git@`,
`ssh://`, `file://`, `/` dışında) ya da `-` ile başlıyorsa; önbellek dizini
varsa ama git deposu değilse; `--ref` boşsa, boşluk içeriyorsa, `-` ile
başlıyorsa, `..` içeriyorsa ya da `:`, `*`, `^`, `~`, `@`, ters bölü
karakterlerinden birini içeriyorsa.
"""

from __future__ import annotations

import argparse
import json
import re
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


FORBIDDEN_REF_CHARS = ":*^~@\\"


def validate_ref(value: str) -> str:
    """`--ref` değerini doğrula: argv'ye ve revizyon adına güvenli olmalı.

    Boş, boşluk içeren, `-` ile başlayan (git seçeneği gibi okunur), `..`
    içeren (revizyon aralığı) ve refspec meta karakteri (`:`, `*`, `^`, `~`,
    `@`, ters bölü) içeren değerler reddedilir; aksi halde ref bir refspec gibi
    yorumlanabilir.
    """
    if not value:
        raise ValueError("--ref boş olamaz")
    if any(char.isspace() for char in value):
        raise ValueError(f"--ref boşluk içeremez: {value!r}")
    if value.startswith("-"):
        raise ValueError(f"--ref '-' ile başlayamaz: {value}")
    if ".." in value:
        raise ValueError(f"--ref '..' içeremez: {value}")
    if any(char in value for char in FORBIDDEN_REF_CHARS):
        raise ValueError(
            f"--ref refspec karakteri içeremez ({FORBIDDEN_REF_CHARS}): {value!r}"
        )
    return value


def is_git_repo(path: Path) -> bool:
    """Dizin bir git deposu mu? (`.git` dizini ya da worktree dosyası)"""
    return (path / ".git").exists()


def declared_submodule(project: Path, relative: str) -> bool:
    """`.gitmodules` bu yolu submodule olarak tanımlıyor mu?

    Henüz başlatılmamış submodule'ün kit dizininde `.git` yoktur; mod yine de
    `submodule` olmalıdır. `.gitmodules` git config biçimindedir, bu yüzden
    `[submodule "ad"]` bölümlerindeki `path` satırları okunur.
    """
    path = project / ".gitmodules"
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    target = relative.rstrip("/")
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("["):
            in_section = bool(
                re.match(r'^\[\s*submodule\s+"[^"]*"\s*\]$', stripped)
            )
            continue
        if not in_section:
            continue
        match = re.match(r'^path\s*=\s*(.+?)\s*$', stripped)
        if not match:
            continue
        value = match.group(1).strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if value.rstrip("/") == target:
            return True
    return False


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


def internal_step(name: str, action: str) -> dict:
    """Kabuk komutu olmayan, `--apply` sırasında iç işlemle yürüyen adım."""
    return {"name": name, "internal": action}


def update_config(project: Path, version: str) -> None:
    """Yalnız `kit.version` satırını değiştir; yoksa ekle.

    Dosya yeniden üretilmez: yorumlar, sıra ve satır sonları (CRLF dahil)
    korunur. `kit:` bloğu hiç yoksa sonuna eklenir.
    """
    path = project / CONFIG_NAME
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    in_kit = False
    updated = False
    insert_at: int | None = None
    indent = "  "
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        if re.match(r"^kit:\s*(#.*)?$", body):
            in_kit = True
            insert_at = index + 1
            continue
        if in_kit and re.match(r"^\S", body):
            in_kit = False
            continue
        if not in_kit:
            continue
        if not body.strip():
            continue
        child = re.match(r"^(\s+)\S", body)
        if child and not body.lstrip().startswith("#"):
            indent = child.group(1)
        else:
            continue
        if not updated:
            match = re.match(
                r'^(\s*)version:\s*(?:"[^"]*"|\'[^\']*\'|[^#\r\n]*?)(\s*#.*)?$',
                body,
            )
            if match:
                suffix = match.group(2) or ""
                lines[index] = (
                    f'{match.group(1)}version: "{version}"{suffix}' + line[len(body):]
                )
                updated = True
                continue
        insert_at = index + 1
    if not updated:
        new_line = f'{indent}version: "{version}"{eol}'
        if insert_at is None:
            prefix = "" if not text or text.endswith("\n") else eol
            lines.append(f"{prefix}kit:{eol}{new_line}")
        else:
            if insert_at > 0 and not lines[insert_at - 1].endswith(("\n", "\r")):
                lines[insert_at - 1] += eol
            lines.insert(insert_at, new_line)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("".join(lines))


def relative_kit_path(project: Path, root: Path) -> str:
    """Submodule yolu: proje köküne göre POSIX biçim."""
    try:
        return root.relative_to(project).as_posix()
    except ValueError:
        return str(root)


def build_plan(
    project: Path,
    source: Path | None = None,
    ref: str | None = None,
    skip_skills: bool = False,
    cache_dir: Path | None = None,
) -> dict:
    project = project.resolve()
    config = load_config(project)
    root = kit_root(project, config)
    upstream = upstream_url(config)
    pinned = validate_ref(ref) if ref is not None else None
    ref_name = pinned or DEFAULT_REF
    # Tespit sırası: `self` yalnız kök projenin kendisi *ve* origin upstream ise
    # (`kit.root: "."` tek başına yetmez); sonra kit kökü ayrı bir git deposuysa
    # ya da `.gitmodules` içinde tanımlıysa (henüz başlatılmamış submodule)
    # `submodule`; aksi halde `vendored`.
    mode = "vendored"
    kit_relative = relative_kit_path(project, root)
    if root == project and same_repo(origin_url(project), upstream):
        mode = "self"
    elif root != project and (
        is_git_repo(root) or declared_submodule(project, kit_relative)
    ):
        mode = "submodule"
    cache = Path(cache_dir).expanduser().resolve() if cache_dir else DEFAULT_CACHE
    steps: list[dict] = []

    if mode == "self":
        version = read_version(project)
        steps.append(step("pull", ["git", "-C", project, "pull", "--ff-only"]))
        steps.append(step("doctor", [project / DOCTOR]))
    elif mode == "submodule":
        version = read_version(root) or read_version(project)
        submodule_command = [
            "git",
            "-C",
            project,
            "submodule",
            "update",
            "--init",
        ]
        # `--ref` varsa ağ yalnız bir kez: init kayıtlı commit'e getirir, sonra
        # fetch/checkout pinler. `--remote` yalnız ref yokken.
        if not pinned:
            submodule_command.append("--remote")
        submodule_command.extend(["--", kit_relative])
        steps.append(step("submodule", submodule_command))
        if pinned:
            steps.append(
                step("fetch", ["git", "-C", root, "fetch", "--depth", "1", "origin", "--", pinned])
            )
            steps.append(step("checkout", ["git", "-C", root, "checkout", "--detach", "FETCH_HEAD"]))
        steps.append(internal_step("config", "config"))
        steps.append(step("doctor", [root / DOCTOR, "--product", "--root", project]))
    else:
        local = Path(source).expanduser().resolve() if source else None
        if local is None:
            if not upstream:
                raise ValueError(f"{CONFIG_NAME}: kit.upstream.git yok")
            if cache.exists():
                if not is_git_repo(cache):
                    raise ValueError(f"önbellek bir git deposu değil: {cache}")
                steps.append(
                    step(
                        "fetch",
                        ["git", "-C", cache, "fetch", "--depth", "1", "origin", ref_name],
                    )
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
                            ref_name,
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


def run_internal(item: dict, plan: dict) -> dict:
    """Kabuk komutu olmayan adımı çalıştır (`config`)."""
    name = item["name"]
    if item.get("internal") != "config":
        return {"name": name, "exit_code": 1, "ok": False, "error": "bilinmeyen iç işlem"}
    try:
        version = read_version(Path(plan["kit_root"]))
        if not version:
            raise ValueError(f"VERSION bulunamadı: {plan['kit_root']}")
        update_config(Path(plan["project"]), version)
    except (OSError, ValueError) as exc:
        return {"name": name, "exit_code": 1, "ok": False, "error": str(exc)}
    return {"name": name, "exit_code": 0, "ok": True}


def apply_plan(plan: dict) -> list[dict]:
    """Adımları sırayla çalıştır; ilk hatada dur."""
    results: list[dict] = []
    for item in plan["steps"]:
        if item.get("internal"):
            result = run_internal(item, plan)
            results.append(result)
            if not result["ok"]:
                break
            continue
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


def command_text(item: dict) -> str:
    if item.get("command"):
        return " ".join(item["command"])
    return "(iç işlem)"


def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit güncelle")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="yalnız plan (varsayılan)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source", type=Path, help="yerel kit kökü")
    parser.add_argument("--ref", default=None, help="dal/commit (varsayılan main)")
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
        if plan["mode"] == "submodule":
            # Submodule güncellemesi yalnız pointer'ı değiştirir; commit üründe.
            plan["note"] = "pointer değişti; ürün reposunda commit'le"

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
            command = command_text(item)
            if args.apply:
                mark = "ok" if item["ok"] else "fail"
                print(f"  {mark} {item['name']}: {command}")
            else:
                print(f"  {item['name']}: {command}")
        if plan.get("note"):
            print(f"not: {plan['note']}")

    if args.apply and any(not item["ok"] for item in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
