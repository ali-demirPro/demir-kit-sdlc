#!/usr/bin/env python3
"""Run the suites a checkpoint's changed files require.

Doctor is always run. The changed-file set decides the rest: a change under
``delivery/tests/`` needs the unittest suite, a change under ``plugins/`` needs
the Orca plugin suite.

Usage:
  bash delivery/scripts/gate.sh --issue 208 --checkpoint CP-1
  bash delivery/scripts/gate.sh --plan --changed delivery/tests/test_gate.py --checkpoint CP-1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Kit root: the directory that holds ``delivery/``. In a vendored product this
# is ``<product>/<kit root>/`` because the script ships inside the kit copy.
KIT_ROOT = Path(__file__).resolve().parents[2]

STEP_TIMEOUT = 900
TEST_ROOT = "delivery/tests"
PLUGIN_ROOT = "plugins"
PLUGIN_PATH = "plugins/orca"

CACHE_NAME = "gate-cache.json"
CACHE_TTL = 86_400
CACHE_MAX = 50
CHECKPOINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _git(args: list[str], project: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=str(project),
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    return result.stdout if result.returncode == 0 else None


def _names(args: list[str], project: Path) -> list[str]:
    raw = _git([*args, "-z"], project)
    if raw is None:
        return []
    return [item.strip("\n") for item in raw.split("\0") if item.strip("\n")]


def changed_files(project: Path) -> list[str]:
    """Union of branch, staged/worktree and untracked changes."""
    base = _git(["merge-base", "origin/main", "HEAD"], project)
    if base is None:
        base = _git(["rev-list", "--max-parents=0", "-1", "HEAD"], project)
    paths: set[str] = set()
    if base:
        paths.update(
            _names(
                ["diff", "--name-only", f"{base.strip()}...HEAD"], project
            )
        )
    else:
        print(
            "[gate] uyarı: branch diff alınamadı; yalnız son commit",
            file=sys.stderr,
            flush=True,
        )
    paths.update(_names(["diff", "--name-only", "HEAD"], project))
    paths.update(_names(["ls-files", "--others", "--exclude-standard"], project))
    return sorted(paths)


def _normalize(path: str) -> str:
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def _git_text(args: list[str], project: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=str(project),
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    return result.stdout if result.returncode == 0 else ""


def tracked_changes(project: Path) -> set[str]:
    """Tracked files that differ from HEAD (staged or not)."""
    lines = _git_text(["status", "--porcelain"], project).splitlines()
    return {
        line[3:].strip()
        for line in lines
        if line.strip() and not line.startswith("??")
    }

def working_tree_changes(project: Path) -> set[str]:
    """Tracked *and* untracked paths that differ from HEAD."""
    lines = _git_text(["status", "--porcelain"], project).splitlines()
    return {line[3:].strip() for line in lines if line.strip()}


def tree_state(project: Path) -> str:
    """HEAD + dirty diff + untracked list, hashed."""
    names = [
        name
        for name in _git_text(
            ["ls-files", "--others", "--exclude-standard"], project
        ).splitlines()
        if name.strip()
    ]
    untracked = []
    for name in names:
        path = project / name
        try:
            data = path.read_bytes()[:200_000]
        except OSError:
            data = b""
        untracked.append(name + "\0" + hashlib.sha256(data).hexdigest())
    payload = [
        _git_text(["rev-parse", "HEAD"], project),
        _git_text(["diff", "--binary", "HEAD"], project),
        "\n".join(untracked),
    ]
    return hashlib.sha256("\0".join(payload).encode("utf-8")).hexdigest()


def tool_version() -> str:
    version = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        return version.read_text(encoding="utf-8").strip()
    except OSError:
        return "?"


def cache_path(project: Path) -> Path:
    return Path(project) / ".kit" / CACHE_NAME


def load_cache(project: Path) -> dict:
    path = cache_path(project)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(project: Path, data: dict) -> None:
    path = cache_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def cache_key(
    project: Path, steps: list[str], checkpoint: str, issue: int | None = None
) -> str:
    payload = json.dumps(
        {
            "tree": tree_state(project),
            "steps": steps,
            "checkpoint": checkpoint,
            "issue": issue,
            "version": tool_version(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_lookup(project: Path, key: str, now: float | None = None) -> dict | None:
    data = load_cache(project)
    entry = data.get(key)
    if not isinstance(entry, dict):
        return None
    if now is None:
        now = time.time()
    try:
        stamp = float(entry.get("ts") or 0)
    except (TypeError, ValueError):
        return None
    if now - stamp > CACHE_TTL:
        return None
    return entry


def cache_store(
    project: Path, key: str, code: int, output: str, command: str = ""
) -> None:
    data = load_cache(project)
    now = time.time()
    data[key] = {
        "ts": now,
        "code": int(code),
        "output": output[-4000:],
        "command": command,
    }
    fresh = sorted(
        ((k, v) for k, v in data.items() if isinstance(v, dict)),
        key=lambda item: float(item[1].get("ts") or 0),
        reverse=True,
    )[:CACHE_MAX]
    save_cache(project, dict(fresh))


def product_behavior(project: Path, checkpoint: str) -> list[str]:
    """Behavior commands declared by a product's ecosystem surfaces.

    The kit's own repository is skipped: its ecosystem points back at gate.sh and
    would recurse. Installed products run their real gate command.
    """
    if project.resolve() == KIT_ROOT.resolve():
        return []
    path = project / "ecosystem.yaml"
    if not path.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    commands: list[str] = []
    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, dict):
        return []
    for product in products.values():
        surfaces = (product or {}).get("surfaces") if isinstance(product, dict) else None
        if not isinstance(surfaces, dict):
            continue
        for surface in surfaces.values():
            gates = (surface or {}).get("gates") if isinstance(surface, dict) else None
            if not isinstance(gates, dict):
                continue
            command = str(gates.get("behavior") or "").strip()
            if not command or "gate.sh" in command:
                continue
            command = command.replace("{checkpoint}", checkpoint)
            if command not in commands:
                commands.append(command)
    return commands


def product_fix(project: Path, checkpoint: str) -> list[str]:
    """Corrective commands a product surface declares under ``gates.fix``."""
    if project.resolve() == KIT_ROOT.resolve():
        return []
    path = project / "ecosystem.yaml"
    if not path.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    commands: list[str] = []
    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, dict):
        return []
    for product in products.values():
        surfaces = (product or {}).get("surfaces") if isinstance(product, dict) else None
        if not isinstance(surfaces, dict):
            continue
        for surface in surfaces.values():
            gates = (surface or {}).get("gates") if isinstance(surface, dict) else None
            if not isinstance(gates, dict):
                continue
            command = str(gates.get("fix") or "").strip()
            if not command or "gate.sh" in command:
                continue
            command = command.replace("{checkpoint}", checkpoint)
            if command not in commands:
                commands.append(command)
    return commands


def suites_for(paths: list[str]) -> list[str]:
    """Suites selected by changed paths, in run order."""
    normalized = [_normalize(path) for path in paths]
    suites: list[str] = []
    if any(_under(path, TEST_ROOT) for path in normalized):
        suites.append("unittest")
    if any(_under(path, PLUGIN_ROOT) for path in normalized):
        suites.append("plugin")
    return suites


def doctor_command(
    project: Path, issue: int | None, checkpoint: str
) -> list[str]:
    script = KIT_ROOT / "delivery" / "scripts" / "doctor.sh"
    try:
        display = "./" + str(script.relative_to(project))
    except ValueError:
        display = str(script)
    command = [display]
    if issue is not None:
        command += ["--issue", str(issue)]
    command += ["--checkpoint", checkpoint]
    if KIT_ROOT != project:
        command += ["--product", "--root", "."]
    return command


def step_command(
    step: str, project: Path, issue: int | None, checkpoint: str
) -> list[str]:
    if step == "doctor":
        return doctor_command(project, issue, checkpoint)
    if step == "unittest":
        return ["python3", "-m", "unittest", "discover", "-s", TEST_ROOT]
    if step == "plugin":
        return ["orca", "plugin", "test", PLUGIN_PATH]
    raise ValueError(f"bilinmeyen adım: {step}")


def _run(command: list[str] | str, project: Path, shell: bool = False) -> int:
    try:
        return subprocess.run(
            command,
            cwd=str(project),
            timeout=STEP_TIMEOUT,
            shell=shell,
        ).returncode
    except subprocess.TimeoutExpired:
        print(f"[gate] timeout: {STEP_TIMEOUT}s aşıldı", flush=True)
        return 124
    except (FileNotFoundError, OSError):
        return 127


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="checkpoint gate")
    parser.add_argument("--issue", type=int, help="seal + evidence doğrula (opsiyonel)")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--plan", action="store_true", help="adımları yaz, çalıştırma")
    parser.add_argument("--fast", action="store_true", help="yalnız statik doctor (CP)")
    parser.add_argument("--cached", action="store_true", help="tree hash cache'ini kullan")
    parser.add_argument("--no-cache", action="store_true", help="cache'i baypas et")
    parser.add_argument("--fix", action="store_true", help="düzeltici adımlara izin ver")
    parser.add_argument("--project", type=Path, default=None, help="proje kökü")
    parser.add_argument(
        "--changed",
        action="append",
        default=None,
        metavar="PATH",
        help="git yerine bu değişen dosyaları kullan (tekrarlanabilir)",
    )
    args = parser.parse_args(argv)
    if not CHECKPOINT_RE.fullmatch(args.checkpoint or ""):
        parser.error(
            "--checkpoint yalnız harf, rakam, nokta, alt çizgi ve tire içerir"
        )
    if args.changed is not None and not args.plan:
        parser.error("--changed yalnız --plan ile kullanılabilir")

    project = (args.project or Path.cwd()).resolve()
    paths = (
        list(args.changed)
        if args.changed is not None
        else changed_files(project)
    )
    if args.changed is not None:
        for path in paths:
            if not (project / path).exists():
                print(
                    f"[gate] uyarı: --changed yolu yok: {path}",
                    file=sys.stderr,
                    flush=True,
                )
    behavior = [] if args.fast else product_behavior(project, args.checkpoint)
    steps = ["doctor"] if args.fast else ["doctor", *suites_for(paths)]
    if not args.fast:
        print("[gate] level full", flush=True)
    else:
        print("[gate] level fast", flush=True)

    if args.plan:
        for command in behavior:
            print(f"[gate] plan behavior: {command}", flush=True)
        for step in steps:
            command = step_command(step, project, args.issue, args.checkpoint)
            print(f"[gate] plan {step}: {' '.join(command)}", flush=True)
        return 0

    key = None
    if args.cached and not args.no_cache and not args.fix:
        key = cache_key(project, steps, args.checkpoint, args.issue)
        hit = cache_lookup(project, key)
        if hit is not None:
            print(f"[gate] cache hit {key[:12]} (exit {hit['code']})", flush=True)
            return int(hit["code"])

    if args.fix:
        for command in product_fix(project, args.checkpoint):
            print(f"[gate] fix: {command}", flush=True)
            code = _run(command, project, shell=True)
            print(f"[gate] fix exit {code}", flush=True)
            if code != 0:
                print("[gate] düzeltme adımı düştü", flush=True)
                return 1

    before = working_tree_changes(project)
    failed = False
    executed: list[str] = []
    for command in behavior:
        print(f"[gate] behavior: {command}", flush=True)
        executed.append(command)
        code = _run(command, project, shell=True)
        print(f"[gate] behavior exit {code}", flush=True)
        if code != 0:
            failed = True
    for step in steps:
        if step == "plugin":
            if not shutil.which("orca"):
                print("[gate] plugin skip: orca PATH'te yok", flush=True)
                continue
            if not (project / PLUGIN_PATH).is_dir():
                print(f"[gate] plugin skip: {PLUGIN_PATH} yok", flush=True)
                continue
        command = step_command(step, project, args.issue, args.checkpoint)
        executed.append(" ".join(command))
        code = _run(command, project)
        print(f"[gate] {step} exit {code}", flush=True)
        if code != 0:
            failed = True

    touched = sorted(working_tree_changes(project) - before)
    if touched:
        print(
            "[gate] depo değişti: " + ", ".join(touched[:5])
            + " — kapı salt-okur olmalı; düzeltme ayrı adım (--fix).",
            flush=True,
        )
        failed = True

    if key is not None:
        cache_store(project, key, 1 if failed else 0, "", " && ".join(executed))
    if args.issue is not None:
        try:
            import cycle

            cycle.record(
                cycle.project_root(KIT_ROOT),
                cycle.make_row(
                    args.issue,
                    "gate",
                    actor="gate",
                    reason=(
                        f"{args.checkpoint or '-'} "
                        f"{'fast' if args.fast else 'full'} "
                        f"exit={1 if failed else 0}"
                    ),
                ),
            )
        except Exception:
            pass
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
