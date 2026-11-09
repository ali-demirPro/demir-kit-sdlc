"""Tests for the gate result cache."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("gate_cache", SCRIPTS / "gate.py")
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_store_and_lookup(self) -> None:
        with mock.patch.object(gate, "tree_state", return_value="abc"):
            key = gate.cache_key(self.project, ["doctor"], "CP-1")
        gate.cache_store(self.project, key, 0, "ok")
        hit = gate.cache_lookup(self.project, key)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["code"], 0)

    def test_expired_entry_is_ignored(self) -> None:
        gate.cache_store(self.project, "k", 0, "ok")
        self.assertIsNone(gate.cache_lookup(self.project, "k", now=10**12))

    def test_key_changes_with_tree_and_checkpoint(self) -> None:
        with mock.patch.object(gate, "tree_state", return_value="one"):
            first = gate.cache_key(self.project, ["doctor"], "CP-1")
        with mock.patch.object(gate, "tree_state", return_value="two"):
            second = gate.cache_key(self.project, ["doctor"], "CP-1")
        third = gate.cache_key(self.project, ["doctor"], "CP-2")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)

    def test_cache_is_capped(self) -> None:
        for index in range(gate.CACHE_MAX + 5):
            gate.cache_store(self.project, f"k{index}", 0, "")
        self.assertEqual(len(gate.load_cache(self.project)), gate.CACHE_MAX)

    def test_cache_file_lives_under_kit(self) -> None:
        gate.cache_store(self.project, "k", 0, "")
        self.assertEqual(gate.cache_path(self.project), self.project / ".kit" / "gate-cache.json")
        self.assertTrue(gate.cache_path(self.project).is_file())

    def test_cache_records_the_real_command(self) -> None:
        gate.cache_store(
            self.project, "k", 0, "ok", "gate.sh --issue 1 --checkpoint CP-1"
        )
        entry = gate.load_cache(self.project)["k"]
        self.assertEqual(entry["command"], "gate.sh --issue 1 --checkpoint CP-1")

    def _untracked_git(self, args: list[str], project: Path) -> str:
        if "ls-files" in args:
            return "big.bin\n"
        if "rev-parse" in args:
            return "0123456789abcdef\n"
        return ""

    def test_tree_state_hashes_untracked_past_the_200kb_cut(self) -> None:
        target = self.project / "big.bin"
        target.write_bytes(b"a" * 300_000)
        # Any full read of the untracked file would trip this patch; the digest
        # must come from chunked reads only.
        with mock.patch.object(
            gate, "_git_text", side_effect=self._untracked_git
        ), mock.patch.object(
            Path, "read_bytes", side_effect=AssertionError("full file read")
        ):
            first = gate.tree_state(self.project)
            with open(target, "r+b") as handle:
                handle.seek(250_000)
                handle.write(b"b")
            second = gate.tree_state(self.project)
        self.assertNotEqual(first, second)

    def test_main_stores_the_executed_command(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            with mock.patch.object(gate, "changed_files", return_value=[]), \
                 mock.patch.object(
                     gate, "doctor_command", return_value=["echo", "gate-ran"]
                 ):
                code = gate.main(
                    ["--checkpoint", "CP-1", "--project", directory, "--cached"]
                )
            self.assertEqual(code, 0)
            entry = next(iter(gate.load_cache(project).values()))
            self.assertEqual(entry["command"], "echo gate-ran")


if __name__ == "__main__":
    unittest.main()
