"""Tests for the read-only status CLI contract skeleton."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "delivery" / "scripts" / "status.py"

CONFIG = 'kit:\n  version: "0.0.0"\n'
TOP_LEVEL = {
    "contract_version",
    "generated_at",
    "stale",
    "source",
    "kit",
    "project",
    "epics",
    "counts",
    "warnings",
}


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


class CliTests(unittest.TestCase):
    def test_project_contract(self) -> None:
        proc = run("--json", "--offline", cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = payload(proc)
        self.assertEqual(set(data), TOP_LEVEL)
        self.assertEqual(data["contract_version"], 1)
        self.assertIsInstance(data["stale"], bool)
        self.assertEqual(data["source"], "live")
        self.assertRegex(data["generated_at"], r"^\d{4}-\d{2}-\d{2}T.*Z$")
        self.assertEqual(set(data["kit"]), {"version", "pin", "dirty"})
        self.assertIsInstance(data["kit"]["dirty"], (bool, type(None)))
        self.assertEqual(set(data["project"]), {"name", "profile", "tracker"})
        self.assertEqual(set(data["project"]["tracker"]), {"provider", "repo"})
        self.assertEqual(set(data["counts"]), {"epics", "leaves", "blocked"})
        self.assertTrue(all(isinstance(value, int) for value in data["counts"].values()))
        self.assertIsInstance(data["epics"], list)
        self.assertIsInstance(data["warnings"], list)

    def test_project_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ornek-proje"
            project.mkdir()
            proc = run("--json", "--project", str(project), cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["project"]["name"], "ornek-proje")

            (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
            proc = run("--json", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["project"]["name"], "ornek-proje")

        with tempfile.TemporaryDirectory() as tmp:
            proc = run("--json", cwd=Path(tmp))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("proje", proc.stderr.lower())

        proc = run("--json", "--project", "/nonexistent-proje", cwd=ROOT)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("proje dizini yok", proc.stderr.lower())

    def test_read_only_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            project.mkdir()
            (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
            proc = run("--json", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((project / ".orchestration").exists())


class CacheTests(unittest.TestCase):
    def project(self, tmp: str) -> Path:
        project = Path(tmp) / "p"
        project.mkdir()
        (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
        return project

    def test_cache_written_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            first = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(first.returncode, 0, first.stderr)
            cache = project / ".orchestration" / "status-cache.json"
            self.assertTrue(cache.is_file())
            written = json.loads(cache.read_text(encoding="utf-8"))
            self.assertEqual(set(written), {"saved_at", "args", "data"})

            loaded = payload(first)
            data = written["data"]
            self.assertEqual(data["contract_version"], 1)
            self.assertEqual(loaded["source"], "live")

            second = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(second.returncode, 0, second.stderr)
            cached = payload(second)
            self.assertEqual(cached["source"], "cache")
            self.assertTrue(any("önbellek" in item for item in cached["warnings"]))

    def test_corrupt_cache_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            cache = project / ".orchestration" / "status-cache.json"
            cache.parent.mkdir(parents=True)
            cache.write_text('{"contract_version": 99}', encoding="utf-8")
            proc = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(set(data), TOP_LEVEL)
            self.assertEqual(data["source"], "live")
            self.assertEqual(data["contract_version"], 1)

    def test_shallow_cache_with_null_sections_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            cache = project / ".orchestration" / "status-cache.json"
            cache.parent.mkdir(parents=True)
            broken = {
                "contract_version": 1,
                "generated_at": "2026-01-01T00:00:00Z",
                "stale": False,
                "source": "cache",
                "kit": None,
                "project": None,
                "epics": [],
                "counts": {"epics": 0, "leaves": 0, "blocked": 0},
                "warnings": [],
            }
            cache.write_text(
                json.dumps({"args": {"with_gate": False, "with_cost": False, "full": False},
                            "data": broken}),
                encoding="utf-8",
            )
            proc = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["source"], "live")

            cache.write_text(
                json.dumps({"args": {"with_gate": False, "with_cost": False, "full": False},
                            "data": broken}),
                encoding="utf-8",
            )
            text = run("--cache-ttl", "60", cwd=project)
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("proje:", text.stdout)

    def test_cache_respects_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            run("--json", "--cache-ttl", "60", cwd=project)
            proc = run("--json", "--cache-ttl", "60", "--with-gate", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["source"], "live")
            self.assertTrue(any("--with-gate" in item for item in data["warnings"]))

    def test_expired_and_negative_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            cache = project / ".orchestration" / "status-cache.json"
            cache.parent.mkdir(parents=True)
            cache.write_text('{"args": {}, "data": {}}', encoding="utf-8")
            old = time.time() - 3600
            os.utime(cache, (old, old))
            proc = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["source"], "live")

        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            proc = run("--json", "--cache-ttl", "-5", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("negatif", proc.stderr)
            self.assertFalse((project / ".orchestration").exists())


if __name__ == "__main__":
    unittest.main()
