"""Tests for the review packet builder."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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

    def test_packet_without_findings(self) -> None:
        packet = review_packet.compose_packet(
            ["## Review packet"], "brief", [], "", "", 12_000
        )
        self.assertIn("Açık bulgular", packet)
        self.assertIn("yok", packet)


if __name__ == "__main__":
    unittest.main()
