"""Tests for the review round's `demir-kit-review` writer."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import review_record  # noqa: E402

spec = importlib.util.spec_from_file_location("brief_r", SCRIPTS / "brief.py")
brief = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(brief)

FINDINGS = [
    {
        "id": "AR-1",
        "severity": "blocking",
        "status": "open",
        "note": "Kit'te hiçbir yazıcı ret kaydı üretmiyor",
    },
    {
        "id": "NIT-1",
        "severity": "nit",
        "status": "open",
        "note": "T-2 kendi kaydını baz alıyor",
    },
]


class ReviewRecordTests(unittest.TestCase):
    def record(self, verdict: str = "revise_required") -> dict:
        return review_record.build_record(
            335, "CP-1", verdict, "41b5007", "adversarial-a", FINDINGS
        )

    def test_body_is_the_parser_contract(self) -> None:
        body = review_record.comment_body(self.record())
        self.assertIn("```yaml\ndemir-kit-review", body)
        block = brief.REVIEW_BLOCK_RE.search(body)
        self.assertIsNotNone(block)
        data = yaml.safe_load(block.group(1))
        self.assertEqual(data["issue"], 335)
        self.assertEqual(data["cp"], "CP-1")
        self.assertEqual(data["verdict"], "revise_required")
        self.assertEqual(data["reviewed_commit"], "41b5007")
        self.assertEqual(data["reviewer"], "adversarial-a")
        self.assertEqual(data["findings"][0]["severity"], "blocking")

    def test_revise_required_is_a_rejection(self) -> None:
        comment = {"body": review_record.comment_body(self.record())}
        rejection = brief.comment_rejection(comment)
        self.assertIsNotNone(rejection)
        self.assertEqual(rejection["decision"], "revise_required")
        self.assertEqual(rejection["cp_id"], "CP-1")
        self.assertIn("AR-1:", rejection["reason"])
        self.assertLess(
            rejection["reason"].index("AR-1:"),
            rejection["reason"].index("NIT-1:"),
        )

    def test_approved_is_not_a_rejection(self) -> None:
        comment = {
            "body": review_record.comment_body(self.record("approved"))
        }
        self.assertIsNone(brief.comment_rejection(comment))

    def test_parse_finding_arg(self) -> None:
        item = review_record.parse_finding_arg(
            "NIT-2|nit|open|satır sonu", 1
        )
        self.assertEqual(item["severity"], "nit")
        self.assertEqual(item["note"], "satır sonu")
        item = review_record.parse_finding_arg(
            '{"id": "AR-9", "severity": "blocking", "status": "open"}', 1
        )
        self.assertEqual(item["note"], "-")

    def test_invalid_finding_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            review_record.parse_finding_arg("X|major|open|n", 1)
        with self.assertRaises(SystemExit):
            review_record.parse_finding_arg("X|nit|maybe|n", 1)
        with self.assertRaises(SystemExit):
            review_record.parse_finding_arg("|nit|open|n", 1)

    def test_post_uses_issue_comments_api(self) -> None:
        calls: list[dict] = []

        def fake_run(args, **kwargs):
            calls.append({"args": args, "input": kwargs.get("input")})
            return type("Result", (), {"returncode": 0, "stdout": '{"id": 42}', "stderr": ""})()

        result = review_record.post_comment(
            "x/y", 335, "BODY", run=fake_run
        )
        self.assertEqual(result, "42")
        self.assertEqual(
            calls[0]["args"][-3:],
            ["repos/x/y/issues/335/comments", "--input", "-"],
        )
        self.assertEqual(json.loads(calls[0]["input"])["body"], "BODY")

    def test_post_failure_is_loud(self) -> None:
        def fake_run(args, **kwargs):
            return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()

        with self.assertRaises(SystemExit):
            review_record.post_comment("x/y", 335, "BODY", run=fake_run)


class ReviewRecordCliTests(unittest.TestCase):
    def run_main(self, argv: list[str]):
        out = io.StringIO()
        with patch.object(review_record, "git", return_value="abc123\n"), patch.object(
            sys, "argv", ["review_record.py", *argv]
        ), redirect_stdout(out):
            code = review_record.main()
        return code, out.getvalue()

    def test_dry_run_prints_body(self) -> None:
        code, out = self.run_main(
            [
                "--issue", "335", "--cp", "CP-1",
                "--verdict", "revise_required", "--reviewer", "adversarial-a",
                "--finding", "AR-1|blocking|open|ret kaydı yok",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("demir-kit-review", out)
        self.assertIn("AR-1", out)
        self.assertIn("abc123", out)

    def test_apply_posts_the_record(self) -> None:
        out = io.StringIO()
        with patch.object(review_record, "git", return_value="abc123\n"), patch.object(
            review_record, "post_comment", return_value="55"
        ) as post, patch.object(
            sys,
            "argv",
            [
                "review_record.py", "--issue", "335", "--cp", "CP-1",
                "--verdict", "revise_required", "--reviewer", "adversarial-a",
                "--finding", "AR-1|blocking|open|ret kaydı yok",
                "--repo", "x/y", "--apply", "--json",
            ],
        ), redirect_stdout(out):
            self.assertEqual(review_record.main(), 0)
        self.assertEqual(post.call_args.args[:2], ("x/y", 335))
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["comment_id"], "55")
        self.assertEqual(payload["verdict"], "revise_required")


if __name__ == "__main__":
    unittest.main()
