"""Tests for the human progress comment."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("update", SCRIPTS / "update.py")
update = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(update)

NOW = datetime(2026, 10, 26, 15, 30, tzinfo=timezone.utc)


class UpdateTests(unittest.TestCase):
    def test_progress_comment(self) -> None:
        body = update.render(
            "progress",
            "developer",
            "Wave runner tamamlandı.",
            decision="Önce dry-run yapıldı.",
            problem="İlk agent seçimi yanlıştı.",
            next_step="Epic kapanışı.",
            now=NOW,
        )
        self.assertIn("## İlerleme — 2026-10-26 15:30 UTC", body)
        self.assertIn("**Kim:** developer", body)
        self.assertIn("**Ne oldu:** Wave runner tamamlandı.", body)
        self.assertIn("**Karar:** Önce dry-run yapıldı.", body)
        self.assertIn("**Sorun:** İlk agent seçimi yanlıştı.", body)
        self.assertIn("**Sırada:** Epic kapanışı.", body)
        self.assertIn("**Onay:** gerekmiyor", body)
        self.assertNotIn("```", body)

    def test_summary_comment(self) -> None:
        body = update.render(
            "summary",
            "owner",
            "Epic 6 tamamlandı.",
            next_step="Yeni epic.",
            approval=True,
            ask="Kapanışı onaylıyor musun?",
            now=NOW,
        )
        self.assertIn("## Özet —", body)
        self.assertIn("**Ne bitti:** Epic 6 tamamlandı.", body)
        self.assertIn("**Kalan:** Yeni epic.", body)
        self.assertIn("**Onay:** gerekiyor — Kapanışı onaylıyor musun?", body)

    def test_optional_fields_omitted(self) -> None:
        body = update.render("progress", "ekip", "Bir şey oldu.", now=NOW)
        self.assertNotIn("**Karar:**", body)
        self.assertNotIn("**Sorun:**", body)
        self.assertNotIn("**Sırada:**", body)
        self.assertIn("**Onay:** gerekmiyor", body)

    def test_repo_name_uses_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ecosystem.yaml").write_text("tracker:\n  repo: owner/product\n")
            with patch.object(update.routing, "project_root", return_value=root):
                self.assertEqual(update.repo_name(), "owner/product")

    def test_line_count_stays_short(self) -> None:
        body = update.render(
            "progress",
            "developer",
            "Kısa.",
            decision="Karar.",
            problem="Sorun.",
            next_step="Sırada.",
            now=NOW,
        )
        self.assertLessEqual(len([line for line in body.splitlines() if line.strip()]), 8)

    def test_orca_checkpoint_marks_in_review_on_approval(self) -> None:
        calls: list[list[str]] = []

        def fake(args, **kwargs):
            calls.append(args)
            if "current" in args:
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"result": {"worktree": {"path": "/tmp/epic-1"}}}),
                    stderr="",
                )
            return types.SimpleNamespace(returncode=0, stdout="{}", stderr="")

        with patch.object(update.subprocess, "run", side_effect=fake):
            result = update.orca_checkpoint("progress", "İş bitti", "Sırada", True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "in-review")
        command = calls[-1]
        self.assertIn("--workspace-status", command)
        self.assertIn("in-review", command)
        self.assertIn("--unread", command)
        self.assertIn("path:/tmp/epic-1", command)


if __name__ == "__main__":
    unittest.main()
