#!/usr/bin/env python3
"""Epic-level Orca worktree lifecycle.

One epic = one worktree, one branch, one PR. Leaves reuse the worktree and
commit on the epic branch; the worktree is removed after ``epic-done``.

Usage:
  python3 delivery/scripts/epic_worktree.py ensure --epic 15
  python3 delivery/scripts/epic_worktree.py check --epic 15
  python3 delivery/scripts/epic_worktree.py sync --epic 15
  python3 delivery/scripts/epic_worktree.py remove --epic 15
  python3 delivery/scripts/epic_worktree.py prune --apply
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import routing  # noqa: E402

STATE_DIR = ".orchestration"
MAIN_BRANCHES = {"main", "master"}


class WorktreeError(RuntimeError):
    """A worktree precondition failed; the caller must block source work."""


def project_root(project: Path | None = None) -> Path:
    return Path(project).resolve() if project else routing.project_root(ROOT)


def epic_name(epic: int) -> str:
    return f"epic-{epic}"


def state_path(project: Path, epic: int) -> Path:
    return main_root(project) / STATE_DIR / f"epic-{epic}.json"


def main_root(project: Path) -> Path:
    """The primary checkout, even when called from a linked worktree."""
    result = git(["rev-parse", "--git-common-dir"], project)
    if result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = (project / common).resolve()
        if common.name == ".git":
            return common.parent
    return toplevel(project)


def load_state(project: Path, epic: int) -> dict:
    path = state_path(project, epic)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(project: Path, epic: int, data: dict) -> None:
    path = state_path(project, epic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_config(project: Path) -> dict:
    try:
        data = yaml.safe_load((project / "kit.config.yaml").read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def tracker_repo(project: Path) -> str:
    config = load_config(project)
    repo = (config.get("tracker") or {}).get("repo")
    if repo:
        return str(repo)
    try:
        ecosystem = yaml.safe_load(
            (project / "ecosystem.yaml").read_text(encoding="utf-8")
        ) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return ""
    return str((ecosystem.get("tracker") or {}).get("repo") or "")


def epic_url(project: Path, epic: int) -> str:
    repo = tracker_repo(project)
    return f"https://github.com/{repo}/issues/{epic}" if repo else ""


def set_metadata(project: Path, epic: int) -> None:
    name = epic_name(epic)
    orca_json(
        [
            "worktree",
            "set",
            "--worktree",
            f"name:{name}",
            "--issue",
            str(epic),
            "--comment",
            f"epic #{epic}",
            "--json",
        ],
        project,
    )


def ps(project: Path | None = None) -> dict:
    project = project_root(project)
    return orca_json(["worktree", "ps", "--json"], project) or {}


def set_base_ref(project: Path | None = None, ref: str = "origin/main") -> dict:
    project = project_root(project)
    top = toplevel(project)
    rid = repo_id(project)
    if not rid:
        raise WorktreeError("repo id bulunamadı; önce worktree oluştur")
    payload = orca_json(
        ["repo", "set-base-ref", "--repo", f"id:{rid}", "--ref", ref, "--json"],
        project,
    )
    if not payload or not payload.get("ok"):
        raise WorktreeError(f"repo base ref ayarlanamadı: {top}")
    return payload


def link_reference(project: Path | None, epic: int, url: str) -> dict:
    project = project_root(project)
    payload = orca_json(
        [
            "reference",
            "add",
            url,
            "--worktree",
            f"name:{epic_name(epic)}",
            "--json",
        ],
        project,
    )
    if not payload or not payload.get("ok"):
        raise WorktreeError(f"referans eklenemedi: {url}")
    return payload


def epic_worktree_enabled(project: Path) -> bool:
    orca = load_config(project).get("orca") or {}
    return bool(orca.get("epic_worktree"))


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True
    )


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd)


def toplevel(project: Path) -> Path:
    result = git(["rev-parse", "--show-toplevel"], project)
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return project.resolve()


def orca_json(args: list[str], project: Path) -> dict | None:
    try:
        result = run(["orca", *args], project)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def orca_available(project: Path) -> bool:
    data = orca_json(["status", "--json"], project)
    return bool(data and data.get("ok"))


def worktree_list(project: Path) -> list[dict]:
    data = orca_json(["worktree", "list", "--json"], project)
    result = (data or {}).get("result") or {}
    worktrees = result.get("worktrees") or []
    return [item for item in worktrees if isinstance(item, dict)]


def current_worktree(project: Path) -> dict | None:
    data = orca_json(["worktree", "current", "--json"], project)
    result = (data or {}).get("result") or {}
    worktree = result.get("worktree")
    return worktree if isinstance(worktree, dict) else None


def repo_id(project: Path) -> str | None:
    current = current_worktree(project)
    if current and current.get("repoId"):
        return str(current["repoId"])
    top = toplevel(project)
    for item in worktree_list(project):
        if Path(str(item.get("path") or "")).resolve() == top:
            return str(item.get("repoId") or "") or None
    return None


def find_worktree(project: Path, name: str) -> dict | None:
    rid = repo_id(project)
    for item in worktree_list(project):
        if rid and item.get("repoId") and item.get("repoId") != rid:
            continue
        if item.get("displayName") == name:
            return item
        if Path(str(item.get("path") or "")).name == name:
            return item
    return None


def branch_name(worktree: dict) -> str:
    raw = str(worktree.get("branch") or "")
    return raw[11:] if raw.startswith("refs/heads/") else raw


def _record_from(worktree: dict, epic: int, mode: str) -> dict:
    return {
        "epic": epic,
        "mode": mode,
        "name": epic_name(epic),
        "path": str(worktree.get("path") or ""),
        "branch": branch_name(worktree),
        "worktree_id": worktree.get("id"),
        "run_id": None,
        "tasks": [],
    }


def ensure_run(project: Path, epic: int, record: dict) -> dict:
    if record.get("mode") != "orca":
        return record
    objective = f"epic #{epic}"
    current = orca_json(["orchestration", "run-current", "--json"], project)
    run = ((current or {}).get("result") or {}).get("run")
    if not isinstance(run, dict) or str(run.get("objective") or "") != objective:
        created = orca_json(
            [
                "orchestration",
                "run-create",
                "--objective",
                objective,
                "--json",
            ],
            project,
        )
        run = ((created or {}).get("result") or {}).get("run")
        if not isinstance(run, dict):
            record["run_error"] = (
                "run-create başarısız; epic worktree terminalinden "
                f"`orca orchestration run-create --objective \"{objective}\"` çalıştır"
            )
            return record
    record["run_id"] = run.get("id")
    return record


def _degrade_path(project: Path, epic: int) -> Path:
    repo = main_root(project)
    return repo.parent / f"{repo.name}-{epic_name(epic)}"


def _create_git_worktree(project: Path, epic: int, branch: str, path: Path) -> None:
    repo = main_root(project)
    base = branch
    exists = git(["rev-parse", "--verify", base], repo)
    args = ["worktree", "add", str(path)]
    if exists.returncode == 0:
        args.append(base)
    else:
        args += ["-b", branch, "main"]
    result = git(args, repo)
    if result.returncode != 0:
        raise WorktreeError(
            f"git worktree oluşturulamadı: {result.stderr.strip() or result.stdout.strip()}"
        )


def ensure(
    epic: int,
    project: Path | None = None,
    create: bool = True,
) -> dict:
    project = project_root(project)
    name = epic_name(epic)
    state = load_state(project, epic)
    if state.get("path") and Path(state["path"]).exists():
        if epic_worktree_enabled(project):
            state = ensure_run(project, epic, state)
            save_state(project, epic, state)
        return state

    if orca_available(project):
        worktree = find_worktree(project, name)
        if worktree is None and create:
            base_args = [
                "worktree",
                "create",
                "--name",
                name,
                "--issue",
                str(epic),
                "--repo",
                f"path:{toplevel(project)}",
            ]
            link = epic_url(project, epic)
            extras = ["--comment", f"epic #{epic}"]
            if link:
                extras += ["--reference", link]
            payload = orca_json([*base_args, *extras, "--json"], project)
            if (not payload or not payload.get("ok")) and extras:
                # Older Orca without --reference/--comment: retry without metadata.
                payload = orca_json([*base_args, "--json"], project)
            if not payload or not payload.get("ok"):
                message = ""
                if payload:
                    message = str((payload.get("error") or {}).get("message") or "")
                raise WorktreeError(
                    f"orca worktree create başarısız: {message or 'bilinmeyen hata'}"
                )
            result = payload.get("result") or {}
            worktree = result.get("worktree") if isinstance(result.get("worktree"), dict) else None
            worktree = worktree or find_worktree(project, name)
        if worktree is None:
            raise WorktreeError(
                f"{name} worktree yok; `orca worktree create --name {name} --issue {epic}`"
            )
        record = _record_from(worktree, epic, "orca")
        save_state(project, epic, record)
        set_metadata(project, epic)
        if epic_worktree_enabled(project):
            record = ensure_run(project, epic, record)
            save_state(project, epic, record)
        return record

    # Degrade: no Orca, but still one real git worktree per epic.
    path = Path(state.get("path") or _degrade_path(project, epic))
    branch = str(state.get("branch") or name)
    if not path.exists():
        _create_git_worktree(project, epic, branch, path)
    record = {
        "epic": epic,
        "mode": "degrade",
        "name": name,
        "path": str(path),
        "branch": branch,
        "worktree_id": None,
        "run_id": None,
        "tasks": [],
        "degrade_reason": "Orca kullanılamıyor; git worktree ile devam edildi.",
    }
    save_state(project, epic, record)
    return record


def check(epic: int, project: Path | None = None) -> dict:
    project = project_root(project)
    if not epic_worktree_enabled(project):
        return {"ok": True, "mode": "disabled", "epic": epic, "reason": "epic_worktree kapalı"}

    name = epic_name(epic)
    state = load_state(project, epic)
    current = current_worktree(project) if orca_available(project) else None
    top = toplevel(project)

    if current:
        path = Path(str(current.get("path") or "")).resolve()
        display = str(current.get("displayName") or "")
        branch = branch_name(current)
        if current.get("isMainWorktree") or path == top:
            raise WorktreeError(
                f"ana checkout'tasın; `{name}` worktree'sine geç: "
                f"`orca worktree activate {name}` veya `cd {state.get('path') or '<epic path>'}`"
            )
        if display != name and path.name != name:
            raise WorktreeError(
                f"yanlış worktree: {display or path.name}; bu epic için `{name}` gerekli"
            )
        if branch in MAIN_BRANCHES:
            raise WorktreeError(f"{name} main branch'inde; epic branch'ine geç")
        if epic_worktree_enabled(project) and not state.get("run_id"):
            raise WorktreeError(
                f"{name} için orchestration run yok; "
                f"`orca orchestration run-create --objective \"epic #{epic}\"`"
            )
        return {
            "ok": True,
            "mode": "orca",
            "epic": epic,
            "name": name,
            "path": str(path),
            "branch": branch,
            "run_id": state.get("run_id"),
        }

    # No Orca: accept the degraded git worktree only when it is not the main checkout.
    if state.get("mode") == "degrade":
        path = Path(str(state.get("path") or "")).resolve()
        if path.exists() and path == top:
            return {
                "ok": True,
                "mode": "degrade",
                "epic": epic,
                "name": name,
                "path": str(path),
                "branch": state.get("branch"),
                "reason": state.get("degrade_reason"),
            }

    raise WorktreeError(
        f"Orca worktree `{name}` bulunamadı ve ana checkout kullanılıyor; "
        f"önce `python3 delivery/scripts/epic_worktree.py ensure --epic {epic}`"
    )


def sync(epic: int, project: Path | None = None, remote: str = "origin") -> dict:
    project = project_root(project)
    state = load_state(project, epic)
    path = Path(str(state.get("path") or ""))
    if not path.is_dir():
        raise WorktreeError(f"{epic_name(epic)} worktree yok; önce ensure çalıştır")
    branch = str(state.get("branch") or "")
    if branch in MAIN_BRANCHES:
        raise WorktreeError("main branch'te sync yapılmaz")
    fetched = git(["fetch", remote], path)
    if fetched.returncode != 0:
        raise WorktreeError(f"git fetch başarısız: {fetched.stderr.strip()}")
    merged = git(["merge", "--no-edit", f"{remote}/main"], path)
    if merged.returncode != 0:
        raise WorktreeError(
            "main merge edilemedi (rebase yasak): "
            + (merged.stderr.strip() or merged.stdout.strip())
        )
    return {
        "epic": epic,
        "path": str(path),
        "branch": branch,
        "merged": f"{remote}/main",
        "stdout": merged.stdout.strip(),
    }


def remove(
    epic: int,
    project: Path | None = None,
    force: bool = False,
    keep_branch: bool = False,
) -> dict:
    project = project_root(project)
    state = load_state(project, epic)
    name = epic_name(epic)
    path = Path(str(state.get("path") or ""))
    mode = state.get("mode")

    if mode == "orca" or (not mode and orca_available(project)):
        args = ["worktree", "rm", "--worktree", f"name:{name}", "--json"]
        if force:
            args.append("--force")
        payload = orca_json(args, project)
        if not payload or not payload.get("ok"):
            message = ""
            if payload:
                message = str((payload.get("error") or {}).get("message") or "")
            raise WorktreeError(f"orca worktree rm başarısız: {message or name}")
    elif path.exists():
        repo = toplevel(project)
        args = ["worktree", "remove", str(path)]
        if force:
            args.append("--force")
        result = git(args, repo)
        if result.returncode != 0:
            raise WorktreeError(
                f"git worktree remove başarısız: {result.stderr.strip()}"
            )
        if not keep_branch and state.get("branch"):
            git(["branch", "-d", str(state["branch"])], repo)

    try:
        state_path(project, epic).unlink()
    except FileNotFoundError:
        pass
    return {"epic": epic, "removed": True, "name": name, "path": str(path)}


def _issue_state(project: Path, epic: int) -> str:
    config = load_config(project)
    repo = (config.get("tracker") or {}).get("repo")
    if not repo:
        return ""
    result = run(
        ["gh", "issue", "view", str(epic), "--repo", repo, "--json", "state,labels"],
        project,
    )
    if result.returncode != 0:
        return ""
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    labels = {item.get("name") for item in data.get("labels") or []}
    if data.get("state") == "CLOSED" or "epic-done" in labels:
        return "closed"
    return "open"


def prune(project: Path | None = None, apply: bool = False) -> list[dict]:
    project = project_root(project)
    if not orca_available(project):
        raise WorktreeError("Orca yok; prune yalnız Orca worktree'leri için")
    actions = []
    rid = repo_id(project)
    for item in worktree_list(project):
        if rid and item.get("repoId") and item.get("repoId") != rid:
            continue
        name = str(item.get("displayName") or "")
        if not name.startswith("epic-"):
            continue
        try:
            epic = int(name.split("-", 1)[1])
        except ValueError:
            continue
        if _issue_state(project, epic) != "closed":
            continue
        path = str(item.get("path") or "")
        action = {"epic": epic, "name": name, "path": path, "removed": False}
        if apply:
            payload = orca_json(
                ["worktree", "rm", "--worktree", f"name:{name}", "--json"], project
            )
            action["removed"] = bool(payload and payload.get("ok"))
            try:
                state_path(project, epic).unlink()
            except FileNotFoundError:
                pass
        actions.append(action)
    return actions


def _print(data: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if data.get("error"):
        print(f"epic_worktree: {data['error']}", file=sys.stderr)
        return
    if data.get("action") == "prune":
        if not data["items"]:
            print("temizlenecek epic worktree yok")
        for item in data["items"]:
            state = "silindi" if item["removed"] else "aday"
            print(f"{item['name']}  {item['path']}  [{state}]")
        return
    if data.get("action") == "check":
        print(
            f"ok: {data['name']} · {data.get('branch')} · "
            f"{data.get('path')} · run {data.get('run_id') or '-'}"
        )
        return
    if data.get("action") == "sync":
        print(f"synced: {data['path']} ← {data['merged']}")
        return
    if data.get("action") == "remove":
        print(f"removed: {data['name']} ({data['path']})")
        return
    if data.get("action") == "ps":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if data.get("action") in {"base-ref", "reference"}:
        print("ok")
        return
    print(
        f"{data['name']}: {data['path']} · branch {data.get('branch')} · "
        f"run {data.get('run_id') or '-'} · {data.get('mode')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="epic-level worktree lifecycle")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    ensure_p = sub.add_parser("ensure")
    common(ensure_p)
    ensure_p.add_argument("--epic", type=int, required=True)
    ensure_p.add_argument("--no-create", action="store_true")

    check_p = sub.add_parser("check")
    common(check_p)
    check_p.add_argument("--epic", type=int, required=True)

    sync_p = sub.add_parser("sync")
    common(sync_p)
    sync_p.add_argument("--epic", type=int, required=True)

    remove_p = sub.add_parser("remove")
    common(remove_p)
    remove_p.add_argument("--epic", type=int, required=True)
    remove_p.add_argument("--force", action="store_true")
    remove_p.add_argument("--keep-branch", action="store_true")

    prune_p = sub.add_parser("prune")
    common(prune_p)
    prune_p.add_argument("--apply", action="store_true")

    ps_p = sub.add_parser("ps")
    common(ps_p)

    base_p = sub.add_parser("base-ref")
    common(base_p)
    base_p.add_argument("--ref", default="origin/main")

    ref_p = sub.add_parser("reference")
    common(ref_p)
    ref_p.add_argument("--epic", type=int, required=True)
    ref_p.add_argument("--url", required=True)

    args = parser.parse_args()
    try:
        if args.command == "ensure":
            data = ensure(args.epic, args.project, create=not args.no_create)
            data["action"] = "ensure"
        elif args.command == "check":
            data = check(args.epic, args.project)
            data["action"] = "check"
        elif args.command == "sync":
            data = sync(args.epic, args.project)
            data["action"] = "sync"
        elif args.command == "remove":
            data = remove(
                args.epic,
                args.project,
                force=args.force,
                keep_branch=args.keep_branch,
            )
            data["action"] = "remove"
        elif args.command == "ps":
            data = {"action": "ps", **ps(args.project)}
        elif args.command == "base-ref":
            data = {"action": "base-ref", **set_base_ref(args.project, args.ref)}
        elif args.command == "reference":
            data = {
                "action": "reference",
                **link_reference(args.project, args.epic, args.url),
            }
        else:
            data = {
                "action": "prune",
                "items": prune(args.project, apply=args.apply),
            }
    except WorktreeError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"epic_worktree: {exc}", file=sys.stderr)
        return 1
    _print(data, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
