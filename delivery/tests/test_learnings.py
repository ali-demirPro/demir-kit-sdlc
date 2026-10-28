"""Tests for fleet learning federation (self-improvement lane)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("learnings", SCRIPTS / "learnings.py")
learnings = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(learnings)


def record(repo: str, number: int, title: str, body: str = "") -> dict:
    return learnings.normalize({"number": number, "title": title, "body": body}, repo)


class ClassifyTests(unittest.TestCase):
    def test_gate_retry(self) -> None:
        rec = record("o/a", 1, "behavior gate tekrar düşüyor")
        self.assertEqual(rec["class"], "gate-retry")

    def test_risk_glob_is_auto(self) -> None:
        rec = record("o/a", 2, "yeni risk glob: `**/crypto/**` escalate edilsin")
        self.assertEqual(rec["proposed_change"]["kind"], "risk_glob_add")
        self.assertTrue(rec["proposed_change"]["auto"])

    def test_code_change_is_manual(self) -> None:
        rec = record("o/a", 3, "detect.py monorepo tarama derinliği")
        self.assertEqual(rec["proposed_change"]["kind"], "code_change")
        self.assertFalse(rec["proposed_change"]["auto"])

    def test_capability_is_manual(self) -> None:
        rec = record("o/a", 4, "yeni capability: domain.crypto")
        self.assertEqual(rec["proposed_change"]["kind"], "capability_add")
        self.assertFalse(rec["proposed_change"]["auto"])


class DigestTests(unittest.TestCase):
    def test_two_repos_become_candidate(self) -> None:
        records = [
            record("o/a", 1, "behavior gate tekrar düşüyor"),
            record("o/b", 7, "behavior gate tekrar fail oldu"),
        ]
        items = learnings.digest(records)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "candidate")
        self.assertEqual(items[0]["occurrences"], 2)
        self.assertEqual(items[0]["repos"], ["o/a", "o/b"])

    def test_single_repo_stays_local(self) -> None:
        records = [
            record("o/a", 1, "behavior gate tekrar düşüyor"),
            record("o/a", 2, "behavior gate tekrar fail"),
        ]
        items = learnings.digest(records)
        self.assertEqual(items[0]["status"], "local")


class ApplyTests(unittest.TestCase):
    def make_root(self, directory: str) -> Path:
        root = Path(directory)
        (root / "delivery").mkdir()
        (root / "delivery" / "registry.yaml").write_text(
            'risk:\n  auto_escalate:\n    high:\n      - "**/auth/**"\n',
            encoding="utf-8",
        )
        (root / "VERSION").write_text("2.0.0\n", encoding="utf-8")
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## 2.0.0 — 2026-01-01\n", encoding="utf-8"
        )
        return root

    def test_risk_glob_add_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            rec = record("o/a", 9, "yeni risk glob: `**/crypto/**`")
            first = learnings.apply_risk_glob_add(root, rec)
            second = learnings.apply_risk_glob_add(root, rec)
            self.assertTrue(first.startswith("applied:"))
            self.assertIn("skip", second)
            text = (root / "delivery" / "registry.yaml").read_text(encoding="utf-8")
            self.assertEqual(text.count("**/crypto/**"), 1)

    def test_manual_kind_not_in_whitelist(self) -> None:
        rec = record("o/a", 10, "detect.py tarama derinliği artmalı")
        self.assertEqual(rec["proposed_change"]["kind"], "code_change")
        self.assertFalse(rec["proposed_change"]["auto"])
        self.assertNotIn(rec["proposed_change"]["kind"], learnings.AUTO_KINDS)

    def test_version_bump(self) -> None:
        self.assertEqual(learnings.bump_patch("2.27.0"), "2.27.1")