"""Tests for the review packet builder."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DEMIR_KIT_CYCLE_ROOT", tempfile.mkdtemp(prefix="kit-cycle-"))
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "review_packet", SCRIPTS / "review_packet.py"
)
review_packet = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(review_packet)


def comment(cp_id: str, findings: list[dict]) -> dict:
    import yaml

    block = yaml.safe_dump(
        {"cp_id": cp_id, "findings": findings}, sort_keys=False
    )
    return {"body": f"```yaml\ndemir-kit-evidence\n{block}```\n"}


class ReviewPacketTests(unittest.TestCase):
    def test_commit_range_full_and_delta(self) -> None:
        self.assertEqual(
            review_packet.commit_range("abc", None), "abc^..abc"
        )
        self.assertEqual(
            review_packet.commit_range("abc", "base"), "base..abc"
        )

    def test_open_findings_only_open(self) -> None:
        comments = [
            comment(
                "CP-1",
                [
                    {"id": "ADV-1", "status": "open", "note": "açık"},
                    {"id": "ADV-2", "status": "fixed", "note": "kapalı"},
                ],
            ),
            {"body": "not evidence"},
        ]
        rows = review_packet.open_findings(comments)
        self.assertEqual([row["id"] for row in rows], ["ADV-1"])
        self.assertEqual(rows[0]["cp_id"], "CP-1")

    def test_packet_has_scope_findings_and_diff(self) -> None:
        packet = review_packet.compose_packet(
            ["## Review packet — #1 CP-1"],
            "## CP brief\n- AC-1: kapsam",
            [{"id": "ADV-1", "cp_id": "CP-1", "note": "düzelt"}],
            " delivery/a.py | 2 +-",
            "diff --git a/a.py b/a.py\n+new",
            12_000,
        )
        self.assertIn("AC-1", packet)
        self.assertIn("ADV-1", packet)
        self.assertIn("diff --git", packet)
        self.assertIn("Reviewer kontrolü", packet)
        self.assertLessEqual(len(packet.encode("utf-8")), 12_000)

    def test_packet_truncates_diff(self) -> None:
        packet = review_packet.compose_packet(
            ["## Review packet"],
            "## CP brief\n- AC-1",
            [],
            "",
            "x" * 20_000,
            800,
        )
        self.assertIn("diff kısaltıldı", packet)
        self.assertLessEqual(len(packet.encode("utf-8")), 800)

    def test_findings_use_latest_status(self) -> None:
        comments = [
            comment("CP-1", [{"id": "ADV-1", "status": "open", "note": "eski"}]),
            comment("CP-1", [{"id": "ADV-1", "status": "fixed", "note": "yeni"}]),
        ]
        self.assertEqual(review_packet.open_findings(comments), [])
        self.assertEqual(
            [row["id"] for row in review_packet.open_findings(list(reversed(comments)))],
            ["ADV-1"],
        )

    def test_tiny_max_chars_is_hard_limit(self) -> None:
        packet = review_packet.compose_packet(
            ["## Review packet"],
            "brief " * 100,
            [],
            "",
            "diff " * 100,
            200,
        )
        self.assertLessEqual(len(packet.encode("utf-8")), 200)

    def test_non_ascii_limit_is_bytes(self) -> None:
        packet = review_packet.compose_packet(
            ["## Review packet"],
            "Türkçe bağlam " * 200,
            [],
            "",
            "ııı" * 1000,
            500,
        )
        self.assertLessEqual(len(packet.encode("utf-8")), 500)
        self.assertIn("kısalt", packet)

    def test_packet_without_findings(self) -> None:
        packet = review_packet.compose_packet(
            ["## Review packet"], "brief", [], "", "", 12_000
        )
        self.assertIn("Açık bulgular", packet)
        self.assertIn("yok", packet)


SEAL_BODY = """```yaml demir-kit
epic: 149
risk: {level: low}
surfaces: [kit.docs]
acceptance_criteria: [{id: AC-1, text: kapsam}]
tests_plan:
  - checkpoint_id: CP-1
    cases: [{id: T-1, ac: AC-1, text: test, check: unit}]
checkpoints:
  - {id: CP-1, title: T, gates: {behavior: true}}
```
"""


class ReviewPacketCliTests(unittest.TestCase):
    def fake_gh(self, args: list[str]) -> str:
        if "comments" in args[-1]:
            return json.dumps([])
        return json.dumps({"body": SEAL_BODY})

    def fake_git(self, calls: list[list[str]]):
        def run(args: list[str]) -> str:
            calls.append(args)
            if args[0] == "rev-parse":
                return "abc123\n"
            if args[:2] == ["diff", "--stat"]:
                return " a.py | 1 +\n"
            return "diff --git a/a.py b/a.py\n+new\n"

        return run

    def run_cli(self, argv: list[str]):
        out = io.StringIO()
        with patch.object(review_packet, "gh", side_effect=self.fake_gh), patch.object(
            review_packet, "git", side_effect=self.fake_git([])
        ), patch.object(review_packet.brief, "render_cp_brief", return_value="BRIEF"), patch.object(
            sys, "argv", ["review_packet.py", *argv]
        ), redirect_stdout(out):
            code = review_packet.main()
        return code, out.getvalue()

    def test_delta_json(self) -> None:
        calls: list[list[str]] = []
        out = io.StringIO()
        with patch.object(review_packet, "gh", side_effect=self.fake_gh), patch.object(
            review_packet, "git", side_effect=self.fake_git(calls)
        ), patch.object(
            review_packet.brief, "render_cp_brief", return_value="BRIEF"
        ) as render, patch.object(
            sys, "argv",
            ["review_packet.py", "--issue", "144", "--cp", "CP-1", "--delta", "base", "--json"],
        ), redirect_stdout(out):
            self.assertEqual(review_packet.main(), 0)
        self.assertFalse(render.call_args.kwargs["include_evidence"])
        data = json.loads(out.getvalue())
        self.assertEqual(data["delta"], "base")
        self.assertTrue(any(args[:2] == ["diff", "base..abc123"] for args in calls))

    def test_base_range(self) -> None:
        calls: list[list[str]] = []
        out = io.StringIO()
        with patch.object(review_packet, "gh", side_effect=self.fake_gh), patch.object(
            review_packet, "git", side_effect=self.fake_git(calls)
        ), patch.object(review_packet.brief, "render_cp_brief", return_value="BRIEF"), patch.object(
            sys, "argv",
            ["review_packet.py", "--issue", "144", "--cp", "CP-1", "--base", "parent", "--json"],
        ), redirect_stdout(out):
            self.assertEqual(review_packet.main(), 0)
        self.assertTrue(any(args[:2] == ["diff", "parent..abc123"] for args in calls))

    def test_write_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, out = self.run_cli(
                ["--issue", "144", "--cp", "CP-1", "--write", directory]
            )
            self.assertEqual(code, 0)
            path = Path(out.strip())
            self.assertTrue(path.is_file())
            self.assertIn("BRIEF", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
