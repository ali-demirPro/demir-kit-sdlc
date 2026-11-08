"""Tests for the fleet audit."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("audit", SCRIPTS / "audit.py")
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


def make_db(path: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE session_v2 (
            id text PRIMARY KEY,
            parent_id text,
            directory text NOT NULL,
            title text,
            cost real NOT NULL,
            tokens_cache_read integer NOT NULL,
            time_created integer NOT NULL,
            time_updated integer NOT NULL
        )
        """
    )
    now_ms = int(time.time() * 1000)
    for index, row in enumerate(rows):
        conn.execute(
            "insert into session_v2 values (?,?,?,?,?,?,?,?)",
            (
                f"ses_{index}",
                row.get("parent"),
                row["dir"],
                "t",
                row.get("cost", 0.0),
                row.get("cache", 0),
                now_ms - int(row.get("age_days", 1) * 86_400_000),
                now_ms - int(row.get("age_days", 1) * 86_400_000) + int(row.get("minutes", 10) * 60_000),
            ),
        )
    conn.commit()
    conn.close()


class CollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects = self.root / "Projects"
        self.projects.mkdir()
        self.db = self.root / "opencode.db"
        self.derived = self.root / "DerivedData"
        self.derived.mkdir()
        (self.derived / "votum-abc").mkdir()
        (self.derived / "votum-abc" / "f.bin").write_bytes(b"x" * 1024)
        (self.derived / "votum-def").mkdir()
        make_db(
            self.db,
            [
                {"dir": "/x/Projects/votum", "cache": 100_000_000, "cost": 1.0, "minutes": 40},
                {"dir": "/x/orca/workspaces/votum/epic-70", "parent": "ses_0", "cache": 50_000_000, "cost": 0.5, "minutes": 30},
                {"dir": "/x/Projects/votum", "cache": 10_000_000, "cost": 0.1, "minutes": 600},
                {"dir": "/x/Projects/nombo", "cache": 5_000_000, "cost": 0.2, "minutes": 5, "age_days": 30},
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sessions_are_grouped_per_project(self) -> None:
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        votum = data["projects"]["votum"]
        self.assertEqual(votum["sessions"], 3)
        self.assertEqual(votum["subagents"], 1)
        self.assertEqual(votum["cache_read"], 160_000_000)
        self.assertAlmostEqual(votum["cost"], 1.6, places=3)
        self.assertNotIn("nombo", data["projects"])  # 30 gün önce, pencere dışı

    def test_zombie_and_derived_data_counts(self) -> None:
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        votum = data["projects"]["votum"]
        self.assertEqual(votum["zombies"], 1)
        self.assertEqual(votum["derived_data"], 2)
        self.assertGreater(votum["derived_bytes"], 0)

    def test_cycle_leaf_median(self) -> None:
        kit = self.projects / "votum" / ".kit"
        kit.mkdir(parents=True)
        rows = [
            {"ts": "2026-11-07T10:00:00+00:00", "issue": 1, "stage": "executing"},
            {"ts": "2026-11-07T10:20:00+00:00", "issue": 1, "stage": "leaf-done"},
            {"ts": "2026-11-07T11:00:00+00:00", "issue": 2, "stage": "executing"},
            {"ts": "2026-11-07T11:40:00+00:00", "issue": 2, "stage": "leaf-done"},
        ]
        (kit / "cycle.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
        )
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        self.assertEqual(data["projects"]["votum"]["leaf_median_minutes"], 30)

    def test_review_rounds_and_gates_are_counted(self) -> None:
        kit = self.projects / "votum" / ".kit"
        kit.mkdir(parents=True)
        rows = [
            {"ts": "2026-11-07T10:00:00+00:00", "issue": 1, "stage": "executing"},
            {"ts": "2026-11-07T10:05:00+00:00", "issue": 1, "stage": "review"},
            {"ts": "2026-11-07T10:10:00+00:00", "issue": 1, "stage": "gate"},
            {"ts": "2026-11-07T10:20:00+00:00", "issue": 1, "stage": "leaf-done"},
        ]
        (kit / "cycle.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
        )
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        self.assertEqual(data["projects"]["votum"]["review_rounds"], 1)
        self.assertEqual(data["projects"]["votum"]["gates"], 1)

    def test_review_rounds_come_from_evidence_index(self) -> None:
        kit = self.projects / "votum" / ".kit"
        kit.mkdir(parents=True)
        cycles = [
            {"ts": "2026-11-07T10:00:00+00:00", "issue": 1, "stage": "executing"},
            {"ts": "2026-11-07T10:05:00+00:00", "issue": 1, "stage": "review"},
            {"ts": "2026-11-07T10:10:00+00:00", "issue": 1, "stage": "gate"},
            {"ts": "2026-11-07T10:20:00+00:00", "issue": 1, "stage": "leaf-done"},
        ]
        (kit / "cycle.jsonl").write_text(
            "\n".join(json.dumps(row) for row in cycles) + "\n", encoding="utf-8"
        )
        index = [
            {"ts": "2026-11-07T10:06:00+00:00", "issue": 1, "cp": "CP-1",
             "reviewers": ["ses_real123", None]},
            {"ts": "2026-11-07T10:07:00+00:00", "issue": 1, "cp": "CP-2",
             "reviewers": ["reviewer_a"]},
            {"ts": "2026-11-07T10:08:00+00:00", "issue": 1, "cp": "CP-3",
             "reviewers": []},
        ]
        (kit / "evidence.jsonl").write_text(
            "\n".join(json.dumps(row) for row in index) + "\n", encoding="utf-8"
        )
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        votum = data["projects"]["votum"]
        self.assertTrue(votum["reviews_measured"])
        self.assertEqual(votum["review_rounds"], 1)  # yalnız gerçek kimlik
        self.assertEqual(votum["gates"], 1)

    def test_evidence_index_outside_window_is_ignored(self) -> None:
        kit = self.projects / "votum" / ".kit"
        kit.mkdir(parents=True)
        index = [
            {"ts": "2026-10-01T10:00:00+00:00", "issue": 1, "cp": "CP-1",
             "reviewers": ["ses_old"]},
        ]
        (kit / "evidence.jsonl").write_text(
            "\n".join(json.dumps(row) for row in index) + "\n", encoding="utf-8"
        )
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        votum = data["projects"]["votum"]
        self.assertTrue(votum["reviews_measured"])
        self.assertEqual(votum["review_rounds"], 0)

    def test_render_table_and_recommendations(self) -> None:
        data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        text = audit.render(data)
        self.assertIn("proje", text)
        self.assertIn("votum", text)
        tips = audit.recommend(data)
        self.assertTrue(any("DerivedData" in tip for tip in tips))
        self.assertTrue(any("boşta" in tip for tip in tips))

    def test_read_only_database(self) -> None:
        self.db.chmod(0o444)
        try:
            data = audit.collect(self.projects, days=7, db_path=self.db, derived_root=self.derived)
        finally:
            self.db.chmod(0o644)
        self.assertEqual(data["projects"]["votum"]["sessions"], 3)


class CliTests(unittest.TestCase):
    def test_json_output_has_projects_and_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "db.sqlite"
            make_db(db, [{"dir": "/x/Projects/votum", "cache": 1_000_000, "cost": 0.1}])
            result = __import__("subprocess").run(
                [
                    sys.executable,
                    str(SCRIPTS / "audit.py"),
                    "--projects", str(root / "Projects"),
                    "--db", str(db),
                    "--derived-root", str(root),
                    "--json",
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("projects", payload)
        self.assertIn("recommendations", payload)


if __name__ == "__main__":
    unittest.main()
