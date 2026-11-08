"""Tests for the approval timeout sweep."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("approval_sweep", SCRIPTS / "approval_sweep.py")
sweep = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(sweep)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def stamp(minutes_ago: int) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def request(minutes_ago: int = 61, minutes: int = 60) -> dict:
    body = (
        "## İlerleme\n\n**Onay:** gerekiyor — devam?\n\n"
        "```yaml demir-kit-request\n"
        "issue: 225\n"
        f"asked_at: {stamp(minutes_ago)}\n"
        f"deadline: {stamp(minutes_ago - minutes)}\n"
        f"timeout_minutes: {minutes}\n"
        'ask: "devam?"\n'
        "```\n"
    )
    return {"user": {"login": "agent"}, "author_association": "NONE", "body": body, "created_at": stamp(minutes_ago)}


def human(minutes_ago: int, body: str = "onay") -> dict:
    return {
        "user": {"login": "alidemir"},
        "author_association": "OWNER",
        "body": body,
        "created_at": stamp(minutes_ago),
    }


def timeout_accept(minutes_ago: int = 1) -> dict:
    return {
        "user": {"login": "agent"},
        "author_association": "NONE",
        "body": (
            "```yaml demir-kit-accept\n"
            "decision: accepted\nvia: timeout\nnote: \"60 dk içinde yanıt gelmedi\"\n"
            "```\n"
        ),
        "created_at": stamp(minutes_ago),
    }


class DecideTests(unittest.TestCase):
    def test_expired_request_times_out(self) -> None:
        result = sweep.decide(225, [request()], NOW, risk="low")
        self.assertIsNotNone(result)
        self.assertEqual(result["via"], "timeout")
        self.assertIn("60", result["note"])

    def test_human_answer_wins(self) -> None:
        self.assertIsNone(sweep.decide(225, [request(), human(50)], NOW, risk="low"))

    def test_existing_timeout_is_idempotent(self) -> None:
        self.assertIsNone(
            sweep.decide(225, [request(), timeout_accept()], NOW, risk="low")
        )

    def test_high_risk_gets_a_longer_window(self) -> None:
        self.assertIsNone(sweep.decide(225, [request(61)], NOW, risk="high"))
        result = sweep.decide(225, [request(241, minutes=240)], NOW, risk="high")
        self.assertIsNotNone(result)

    def test_irreversible_has_no_timeout(self) -> None:
        self.assertIsNone(sweep.decide(225, [request(600)], NOW, risk="irreversible"))

    def test_no_request_no_action(self) -> None:
        self.assertIsNone(sweep.decide(225, [human(5)], NOW, risk="low"))


class BlockTests(unittest.TestCase):
    def test_accept_block_carries_note_and_via(self) -> None:
        block = sweep.accept_block(225, "60 dakika içinde yanıt gelmedi")
        self.assertIn("demir-kit-accept", block)
        self.assertIn("via: timeout", block)
        self.assertIn("note:", block)


if __name__ == "__main__":
    unittest.main()
