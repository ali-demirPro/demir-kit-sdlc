"""Tests for the epic-level worktree lifecycle."""

from __future__ import annotations

import importlib.util
import json
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
