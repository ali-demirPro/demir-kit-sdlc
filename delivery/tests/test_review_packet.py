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


def review_comment(
    cp_id: str,
    verdict: str,
    findings: list[dict],
    reviewer: str = "adversarial-a",
    commit: str = "abc123",
    comment_id: int | None = None,
) -> dict:
    """One ``demir-kit-review`` comment in the writer's exact shape."""
    import yaml

    block = yaml.safe_dump(
        {
            "issue": 335,
            "cp": cp_id,
            "verdict": verdict,
            "reviewed_commit": commit,
            "reviewer": reviewer,
            "findings": findings,
        },
        sort_keys=False,
    )
    comment = {"body": f"```yaml\ndemir-kit-review\n{block}```\n"}
    if comment_id is not None:
        comment["id"] = comment_id
    return comment


class ReviewPacketTests(unittest.TestCase):
    def test_commit_range_full_and_delta(self) -> None:
        self.assertEqual(
            review_packet.commit_range("abc", None), "abc^..abc"
        )
        self.assertEqual(
            review_packet.commit_range("abc", "base"), "base..abc"
        )

    def test_issue_commits_skip_a_sibling_leaf(self) -> None:
        """NIT: #335 paketi, aralıktaki #334 commit'ini göstermez."""
        log = (
            "aaa\x1f#335 ilk tur\x1f\x1e"
            "bbb\x1f#334 kardeş leaf\x1f\x1e"
            "ccc\x1f#335 review fix\x1f\x1e"
        )
        with patch.object(review_packet, "git", return_value=log):
            rows = review_packet.issue_commits(335, "aaa..ccc")
        self.assertEqual([row["sha"] for row in rows], ["aaa", "ccc"])

    def test_range_patch_uses_only_issue_commits(self) -> None:
        """NIT: delta aralığında kardeş commit varsa yalnız bu issue'nun
        commit'leri diff'e girer."""
        calls: list[list[str]] = []

        def fake_git(args: list[str]) -> str:
            calls.append(args)
            if args[0] == "log":
                return (
                    "aaa\x1f#335 ilk tur\x1f\x1e"
                    "bbb\x1f#334 kardeş leaf\x1f\x1e"
                    "ccc\x1f#335 review fix\x1f\x1e"
                )
            if args[0] == "show":
                if "--stat" in args:
                    return f" {args[-1]}.py | 1 +\n"
                if "--name-only" in args:
                    return f"{args[-1]}.py\n"
                return f"diff --git a/{args[-1]}.py b/{args[-1]}.py\n"
            return ""

        with patch.object(review_packet, "git", side_effect=fake_git):
            stat, diff, files, filtered = review_packet.range_patch(
                335, "aaa..ccc"
            )
        self.assertTrue(filtered)
        self.assertEqual(files, ["aaa.py", "ccc.py"])
        self.assertNotIn("bbb", diff)
        self.assertIn("aaa.py", stat)
        self.assertNotIn("bbb", stat)
        self.assertFalse(any(args[0] == "diff" for args in calls))

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

    def test_open_findings_read_review_record(self) -> None:
        """Blocking B: açık bulgular `demir-kit-review` kaydından gelir."""
        comments = [
            review_comment(
                "CP-1",
                "revise_required",
                [
                    {"id": "NIT-1", "severity": "nit", "status": "open", "note": "nit"},
                    {
                        "id": "AR-1",
                        "severity": "blocking",
                        "status": "open",
                        "note": "parser ret kaydını görmüyor",
                    },
                    {
                        "id": "AR-2",
                        "severity": "blocking",
                        "status": "fixed",
                        "note": "kapandı",
                    },
                ],
            )
        ]
        rows = review_packet.open_findings(comments)
        self.assertEqual([row["id"] for row in rows], ["AR-1", "NIT-1"])
        self.assertEqual(rows[0]["cp_id"], "CP-1")
        self.assertEqual(rows[0]["note"], "parser ret kaydını görmüyor")

    def test_other_reviewer_approval_keeps_findings_open(self) -> None:
        """Blocking A+B: B onaylasa da A'nın açık bulguları pakette kalır.

        Sahte sha'lar ve yorum id'leri kullanılır: çözüm commit ancestry'sine
        değil yorum sırasına bağlıdır.
        """
        finding = {
            "id": "AR-1",
            "severity": "blocking",
            "status": "open",
            "note": "ret açık",
        }
        comments = [
            review_comment(
                "CP-1", "revise_required", [finding], commit="aaaaaaa", comment_id=11
            ),
            review_comment(
                "CP-1",
                "approved",
                [],
                reviewer="adversarial-b",
                commit="bbbbbbb",
                comment_id=12,
            ),
        ]
        self.assertEqual(
            [row["id"] for row in review_packet.open_findings(comments)],
            ["AR-1"],
        )
        comments.append(
            review_comment(
                "CP-1",
                "approved",
                [],
                reviewer="adversarial-a",
                commit="ccccccc",
                comment_id=13,
            )
        )
        self.assertEqual(review_packet.open_findings(comments), [])

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
            if args[0] == "log":
                return "abc123\x1f#144 fix\x1f\x1e"
            if args[0] == "show":
                if "--stat" in args:
                    return " a.py | 1 +\n"
                if "--name-only" in args:
                    return "a.py\n"
                return "diff --git a/a.py b/a.py\n+new\n"
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
        self.assertTrue(
            any(args[0] == "log" and args[-1] == "base..abc123" for args in calls)
        )
        self.assertTrue(
            any(
                args[0] == "show" and "--patch" in args and "abc123" in args
                for args in calls
            )
        )
        self.assertIn("yalnız #144 commit'leri", data["packet"])

    def test_delta_wins_over_base(self) -> None:
        """NIT: `--delta` verilince paket yalnız o aralığı kullanır."""
        calls: list[list[str]] = []
        out = io.StringIO()
        with patch.object(review_packet, "gh", side_effect=self.fake_gh), patch.object(
            review_packet, "git", side_effect=self.fake_git(calls)
        ), patch.object(
            review_packet.brief, "render_cp_brief", return_value="BRIEF"
        ), patch.object(
            sys,
            "argv",
            [
                "review_packet.py", "--issue", "144", "--cp", "CP-1",
                "--delta", "fixbase", "--base", "wide", "--json",
            ],
        ), redirect_stdout(out):
            self.assertEqual(review_packet.main(), 0)
        self.assertTrue(
            any(args[0] == "log" and args[-1] == "fixbase..abc123" for args in calls)
        )
        self.assertFalse(any("wide..abc123" in args for args in calls))

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
        self.assertTrue(
            any(args[0] == "log" and args[-1] == "parent..abc123" for args in calls)
        )

    def test_cli_lists_review_findings(self) -> None:
        """`review_packet.py --issue 335 --cp CP-1` açık bulguları listeler."""
        review = review_comment(
            "CP-1",
            "revise_required",
            [
                {
                    "id": "AR-1",
                    "severity": "blocking",
                    "status": "open",
                    "note": "stale ret reviewer'ı ayırmıyor",
                }
            ],
        )

        def fake_gh(args: list[str]) -> str:
            if "comments" in args[-1]:
                return json.dumps([review])
            return json.dumps({"body": SEAL_BODY})

        out = io.StringIO()
        with patch.object(review_packet, "gh", side_effect=fake_gh), patch.object(
            review_packet, "git", side_effect=self.fake_git([])
        ), patch.object(
            review_packet.brief, "render_cp_brief", return_value="BRIEF"
        ), patch.object(
            sys,
            "argv",
            ["review_packet.py", "--issue", "335", "--cp", "CP-1", "--json"],
        ), redirect_stdout(out):
            self.assertEqual(review_packet.main(), 0)
        packet = json.loads(out.getvalue())["packet"]
        self.assertIn("## Açık bulgular", packet)
        self.assertIn(
            "- AR-1 (CP-1): stale ret reviewer'ı ayırmıyor", packet
        )

    def test_write_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, out = self.run_cli(
                ["--issue", "144", "--cp", "CP-1", "--write", directory]
            )
            self.assertEqual(code, 0)
            path = Path(out.strip())
            self.assertTrue(path.is_file())
            self.assertIn("BRIEF", path.read_text(encoding="utf-8"))

class GateSummaryTests(unittest.TestCase):
    def write_cache(self, entry: dict) -> Path:
        holder = tempfile.TemporaryDirectory(prefix="kit-gate-")
        self.addCleanup(holder.cleanup)
        directory = Path(holder.name)
        (directory / ".kit").mkdir()
        (directory / ".kit" / "gate-cache.json").write_text(
            json.dumps({"key": entry}), encoding="utf-8"
        )
        return directory

    def test_cached_command_is_reported(self) -> None:
        project = self.write_cache(
            {
                "ts": 1_700_000_000,
                "code": 0,
                "command": "gate.sh --issue 1 --checkpoint CP-1",
            }
        )
        summary = review_packet.gate_summary(project)
        self.assertEqual(summary["source"], "cache")
        self.assertEqual(summary["command"], "gate.sh --issue 1 --checkpoint CP-1")
        self.assertIn("gate.sh --issue 1", review_packet.gate_line(summary))

    def test_missing_command_is_not_invented(self) -> None:
        project = self.write_cache({"ts": 1_700_000_000, "code": 0})
        summary = review_packet.gate_summary(project)
        self.assertEqual(summary["command"], "kayıt yok")


if __name__ == "__main__":
    unittest.main()
