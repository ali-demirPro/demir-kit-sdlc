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
import shutil
import subprocess
import sys
from pathlib import Path

# Kit root: the directory that holds ``delivery/``. In a vendored product this
# is ``<product>/<kit root>/`` because the script ships inside the kit copy.
KIT_ROOT = Path(__file__).resolve().parents[2]

STEP_TIMEOUT = 900
TEST_ROOT = "delivery/tests"
PLUGIN_ROOT = "plugins"
PLUGIN_PATH = "plugins/orca"


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


def _run(command: list[str], project: Path) -> int:
    try:
        return subprocess.run(
            command, cwd=str(project), timeout=STEP_TIMEOUT
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
    parser.add_argument("--project", type=Path, default=None, help="proje kökü")
    parser.add_argument(
        "--changed",
        action="append",
        default=None,
        metavar="PATH",
        help="git yerine bu değişen dosyaları kullan (tekrarlanabilir)",
    )
    args = parser.parse_args(argv)
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
    steps = ["doctor", *suites_for(paths)]

    if args.plan:
        for step in steps:
            command = step_command(step, project, args.issue, args.checkpoint)
            print(f"[gate] plan {step}: {' '.join(command)}", flush=True)
        return 0

    failed = False
    for step in steps:
        if step == "plugin":
            if not shutil.which("orca"):
                print("[gate] plugin skip: orca PATH'te yok", flush=True)
                continue
            if not (project / PLUGIN_PATH).is_dir():
                print(f"[gate] plugin skip: {PLUGIN_PATH} yok", flush=True)
                continue
        command = step_command(step, project, args.issue, args.checkpoint)
        code = _run(command, project)
        print(f"[gate] {step} exit {code}", flush=True)
        if code != 0:
            failed = True

    if args.issue is not None:
        try:
            import cycle

            cycle.record(
                cycle.project_root(KIT_ROOT),
                cycle.make_row(
                    args.issue,
                    "gate",
                    actor="gate",
                    reason=f"{args.checkpoint or '-'} exit={1 if failed else 0}",
                ),
            )
        except Exception:
            pass
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
