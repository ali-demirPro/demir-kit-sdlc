"""Tests for generic keyword suppression in capability matching (#304, #317)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("resolver", SCRIPTS / "resolver.py")
resolver = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(resolver)

REGISTRY = resolver.load_capabilities()


def docs_signal() -> dict:
    return {
        "name": "kit.docs",
        "surfaces": ["kit.docs"],
        "platforms": [],
        "stacks": [],
        "distribution": [],
    }


class GenericKeywordTests(unittest.TestCase):
    def test_generic_tokens_do_not_match_domain_data(self) -> None:
        for text in ("şema", "finding.schema.json"):
            with self.subTest(text=text):
                matched = resolver.match_capabilities(
                    REGISTRY, [docs_signal()], f"Salt-okur doküman leaf'i: {text}."
                )
                self.assertNotIn("domain.data", matched)

    def test_real_data_signals_still_match_domain_data(self) -> None:
        for text in ("migration", "database", "backfill"):
            with self.subTest(text=text):
                matched = resolver.match_capabilities(
                    REGISTRY, [docs_signal()], f"Plan: {text} adımı."
                )
                self.assertIn("domain.data", matched)


if __name__ == "__main__":
    unittest.main()
