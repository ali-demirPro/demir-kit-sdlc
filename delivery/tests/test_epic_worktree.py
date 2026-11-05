"""Tests for the epic-level worktree lifecycle."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "epic_worktree", SCRIPTS / "epic_worktree.py"
)
epic_worktree = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(epic_worktree)


def project(root: Path, enabled: bool = True) -> Path:
    (root / "kit.config.yaml").write_text(
        "orca:\n  epic_worktree: %s\n" % ("true" if enabled else "false"),
        encoding="utf-8",
    )
    return root


def main_worktree(root: Path, repo_id: str = "repo") -> dict:
    return {
        "id": f"{repo_id}::{root}",
        "displayName": "main",
        "path": str(root),
        "branch": "refs/heads/main",
        "repoId": repo_id,
        "isMainWorktree": True,
    }


def epic_worktree_record(root: Path, epic: int = 7, repo_id: str = "repo") -> dict:
    path = root.parent / f"{root.name}-epic-{epic}"
    return {
        "id": f"{repo_id}::{path}",
        "displayName": f"epic-{epic}",
        "path": str(path),
        "branch": f"refs/heads/epic-{epic}",
        "repoId": repo_id,
        "isMainWorktree": False,
    }


class EpicWorktreeTests(unittest.TestCase):
    def test_name_and_state_roundtrip(self) -> None:
        self.assertEqual(epic_worktree.epic_name(15), "epic-15")
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            epic_worktree.save_state(root, 15, {"epic": 15, "path": "/tmp/epic-15"})
            self.assertEqual(
                epic_worktree.load_state(root, 15)["path"], "/tmp/epic-15"
            )
            self.assertTrue(
                (root / ".orchestration" / "epic-15.json").is_file()
            )

    def test_ensure_degrades_to_git_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            expected = root.parent / f"{root.name}-epic-15"

            def create(project_path, epic, branch, path):
                path.mkdir()

            with patch.object(epic_worktree, "orca_available", return_value=False), patch.object(
                epic_worktree, "toplevel", return_value=root
            ), patch.object(
                epic_worktree, "_create_git_worktree", side_effect=create
            ):
                record = epic_worktree.ensure(15, root)
            self.assertEqual(record["mode"], "degrade")
            self.assertEqual(record["path"], str(expected))
            self.assertEqual(epic_worktree.load_state(root, 15)["mode"], "degrade")

    def test_check_is_disabled_without_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), enabled=False)
            result = epic_worktree.check(15, root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "disabled")

    def test_check_blocks_main_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            epic_worktree.save_state(
                root, 15, {"epic": 15, "path": "/tmp/epic-15", "run_id": "run_x"}
            )
            with patch.object(epic_worktree, "orca_available", return_value=True), patch.object(
                epic_worktree, "current_worktree", return_value=main_worktree(root)
            ), patch.object(epic_worktree, "toplevel", return_value=root):
                with self.assertRaises(epic_worktree.WorktreeError) as error:
                    epic_worktree.check(15, root)
            self.assertIn("ana checkout", str(error.exception))

    def test_check_accepts_epic_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            record = epic_worktree_record(root, 15)
            epic_worktree.save_state(
                root,
                15,
                {"epic": 15, "path": record["path"], "run_id": "run_x"},
            )
            with patch.object(epic_worktree, "orca_available", return_value=True), patch.object(
                epic_worktree, "current_worktree", return_value=record
            ), patch.object(epic_worktree, "toplevel", return_value=root):
                result = epic_worktree.check(15, root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["run_id"], "run_x")
            self.assertEqual(result["branch"], "epic-15")

    def test_check_accepts_worktree_when_toplevel_is_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            record = epic_worktree_record(root, 15)
            epic_worktree.save_state(
                root,
                15,
                {"epic": 15, "path": record["path"], "run_id": "run_x"},
            )
            with patch.object(epic_worktree, "orca_available", return_value=True), patch.object(
                epic_worktree, "current_worktree", return_value=record
            ), patch.object(
                epic_worktree, "toplevel", return_value=Path(record["path"]).resolve()
            ), patch.object(epic_worktree, "main_root", return_value=root):
                result = epic_worktree.check(15, root)
            self.assertTrue(result["ok"])
            self.assertEqual(Path(result["path"]), Path(record["path"]).resolve())

    def test_check_requires_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            record = epic_worktree_record(root, 15)
            epic_worktree.save_state(root, 15, {"epic": 15, "path": record["path"]})
            with patch.object(epic_worktree, "orca_available", return_value=True), patch.object(
                epic_worktree, "current_worktree", return_value=record
            ), patch.object(epic_worktree, "toplevel", return_value=root):
                with self.assertRaises(epic_worktree.WorktreeError) as error:
                    epic_worktree.check(15, root)
            self.assertIn("run yok", str(error.exception))

    def test_prune_lists_closed_epics_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory))
            worktrees = [
                epic_worktree_record(root, 7),
                epic_worktree_record(root, 8),
            ]
            with patch.object(epic_worktree, "orca_available", return_value=True), patch.object(
                epic_worktree, "repo_id", return_value="repo"
            ), patch.object(
                epic_worktree, "worktree_list", return_value=worktrees
            ), patch.object(
                epic_worktree,
                "_issue_state",
                side_effect=lambda _root, epic: "closed" if epic == 7 else "open",
            ):
                actions = epic_worktree.prune(root, apply=False)
            self.assertEqual([item["epic"] for item in actions], [7])
            self.assertFalse(actions[0]["removed"])


if __name__ == "__main__":
    unittest.main()


class MainRootIntegrationTests(unittest.TestCase):
    """Real git layouts: main_root must resolve the primary checkout."""

    def make_repo(self, base: Path) -> tuple[Path, Path]:
        import subprocess

        root = base / "repo"
        root.mkdir()

        env = dict(os.environ)
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(key, None)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_SYSTEM"] = os.devnull

        def run(args, cwd):
            subprocess.check_call(
                ["git", "-c", "commit.gpgsign=false", *args],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                env=env,
            )

        run(["init", "-q"], root)
        run(["config", "user.email", "test@example.com"], root)
        run(["config", "user.name", "Test"], root)
        (root / "kit.config.yaml").write_text(
            "orca:\n  epic_worktree: true\n", encoding="utf-8"
        )
        (root / "file.txt").write_text("one\n", encoding="utf-8")
        run(["add", "."], root)
        run(["commit", "-q", "-m", "one"], root)
        linked = base / "linked"
        run(["worktree", "add", "-q", str(linked), "-b", "epic-15"], root)
        return root, linked

    def test_main_root_returns_primary_from_linked_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, linked = self.make_repo(Path(directory))
            self.assertEqual(epic_worktree.main_root(linked).resolve(), root.resolve())
            self.assertEqual(epic_worktree.main_root(root).resolve(), root.resolve())

    def test_check_accepts_linked_and_rejects_primary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, linked = self.make_repo(Path(directory))
            record = {
                "id": "repo::linked",
                "displayName": "epic-15",
                "path": str(linked),
                "branch": "refs/heads/epic-15",
                "repoId": "repo",
                "isMainWorktree": False,
            }
            epic_worktree.save_state(
                root, 15, {"epic": 15, "path": str(linked), "run_id": "run_x"}
            )
            with patch.object(
                epic_worktree, "orca_available", return_value=True
            ), patch.object(epic_worktree, "current_worktree", return_value=record):
                result = epic_worktree.check(15, linked)
            self.assertTrue(result["ok"])

            main_record = dict(record, isMainWorktree=False, path=str(root))
            with patch.object(
                epic_worktree, "orca_available", return_value=True
            ), patch.object(epic_worktree, "current_worktree", return_value=main_record):
                with self.assertRaises(epic_worktree.WorktreeError):
                    epic_worktree.check(15, root)


class RunShapeTests(unittest.TestCase):
    """Orca run payload shapes (1.4 flat vs older nested) resolve to one run id."""

    def ensure(self, responses: dict, record: dict | None = None) -> dict:
        record = record or {"epic": 7, "mode": "orca", "run_id": None, "tasks": []}

        def fake_orca_json(args, _project):
            return responses.get(args[1])

        with patch.object(epic_worktree, "orca_json", side_effect=fake_orca_json):
            return epic_worktree.ensure_run(Path("/tmp/repo"), 7, record)

    def test_flat_run_id(self) -> None:
        record = self.ensure(
            {
                "run-current": {
                    "ok": True,
                    "result": {"runId": "run_flat", "objective": "epic #7"},
                }
            }
        )
        self.assertEqual(record["run_id"], "run_flat")
        self.assertNotIn("run_error", record)

    def test_nested_run_id(self) -> None:
        record = self.ensure(
            {
                "run-current": {
                    "ok": True,
                    "result": {"run": {"id": "run_nested", "objective": "epic #7"}},
                }
            }
        )
        self.assertEqual(record["run_id"], "run_nested")
        self.assertNotIn("run_error", record)

    def test_runs_list_objective_match(self) -> None:
        record = self.ensure(
            {
                "run-current": {
                    "ok": True,
                    "result": {
                        "runs": [
                            {"id": "run_other", "objective": "epic #6"},
                            {"id": "run_right", "objective": "epic #7"},
                        ]
                    },
                }
            }
        )
        self.assertEqual(record["run_id"], "run_right")

    def test_runs_list_other_objective_falls_through(self) -> None:
        record = self.ensure(
            {
                "run-current": {
                    "ok": True,
                    "result": {"runs": [{"id": "run_other", "objective": "epic #6"}]},
                },
                "run-create": {
                    "ok": True,
                    "result": {"runId": "run_new", "objective": "epic #7"},
                },
            }
        )
        self.assertEqual(record["run_id"], "run_new")
        self.assertNotIn("run_error", record)

    def test_no_shape_sets_error(self) -> None:
        record = self.ensure(
            {"run-current": {"ok": True, "result": {}}, "run-create": {"ok": True, "result": {}}}
        )
        self.assertIn("run_error", record)
        self.assertIsNone(record.get("run_id"))

    def test_success_clears_stale_run_error(self) -> None:
        stale = {
            "epic": 7,
            "mode": "orca",
            "run_id": None,
            "tasks": [],
            "run_error": "run-create başarısız; eski hata",
        }
        record = self.ensure(
            {
                "run-current": {
                    "ok": True,
                    "result": {"runId": "run_flat", "objective": "epic #7"},
                }
            },
            record=stale,
        )
        self.assertEqual(record["run_id"], "run_flat")
        self.assertNotIn("run_error", record)

    def test_flat_run_id_wrong_objective(self) -> None:
        payload = {"ok": True, "result": {"runId": "run_6", "objective": "epic #6"}}
        self.assertEqual(epic_worktree.normalize_run(payload, "epic #204"), {})
        self.assertEqual(
            epic_worktree.normalize_run(payload, "epic #6")["id"], "run_6"
        )

    def test_flat_run_id_missing_objective_is_not_a_match(self) -> None:
        payload = {"ok": True, "result": {"runId": "run_x"}}
        self.assertEqual(epic_worktree.normalize_run(payload, "epic #7"), {})
        self.assertEqual(epic_worktree.normalize_run(payload)["id"], "run_x")

    def test_non_string_run_id_rejected(self) -> None:
        for run_id in (123, {"a": 1}, ["run_x"], "", None):
            payload = {"ok": True, "result": {"runId": run_id, "objective": "epic #7"}}
            self.assertEqual(epic_worktree.normalize_run(payload, "epic #7"), {})
            nested = {
                "ok": True,
                "result": {"run": {"id": run_id, "objective": "epic #7"}},
            }
            self.assertEqual(epic_worktree.normalize_run(nested, "epic #7"), {})
            listed = {
                "ok": True,
                "result": {"runs": [{"id": run_id, "objective": "epic #7"}]},
            }
            self.assertEqual(epic_worktree.normalize_run(listed, "epic #7"), {})

    def test_run_list_payload_normalizes(self) -> None:
        payload = {
            "ok": True,
            "result": {
                "runs": [
                    {"id": "run_other", "objective": "epic #6"},
                    {"id": "run_right", "objective": "epic #204"},
                ],
                "nextCursor": None,
            },
        }
        self.assertEqual(
            epic_worktree.normalize_run(payload, "epic #204"),
            {"id": "run_right", "objective": "epic #204"},
        )
        self.assertEqual(epic_worktree.normalize_run(payload, "epic #999"), {})
