"""Tests for registry path routing and the delivery brief."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import routing  # noqa: E402
from kitlib import yamlish  # noqa: E402

spec = importlib.util.spec_from_file_location("brief", SCRIPTS / "brief.py")
brief = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(brief)

REGISTRY = routing.load_registry(ROOT)


def seal(surfaces=("kit.docs",), risk="medium", factory=None) -> str:
    data = {
        "surfaces": list(surfaces),
        "risk": {"level": risk},
    }
    if factory:
        data["factory"] = factory
    return "```yaml demir-kit\n" + yaml.safe_dump(data, sort_keys=False) + "```\n"


class YamlishTests(unittest.TestCase):
    """T-3 and AC-3: one parser, and the D-2 backlog is explicit."""

    # First-pass modules that parse fenced blocks. Each must call the shared
    # parser; usage/cycle carry no YAML block parser at all.
    PARSER_CALLERS = ("routing.py", "next-leaf.py", "closure.py")

    # D-2 (#374) migrates these remaining inline copies. The exact set is the
    # AC-3 measurement: a new copy makes this test red, and so does removing a
    # copy without moving it into the caller set above.
    BACKLOG = {
        "approval_sweep.py",
        "approvals.py",
        "brief.py",
        "cp_close.py",
        "doctor.py",
        "doctor_approval.py",
        "report.py",
        "review_packet.py",
        "seal_lint.py",
        "status.py",
        "transition.py",
    }

    INLINE_PARSER = re.compile(r"```yaml\\s\+[^\n]*\(\.\*\?\)")

    def test_parse_block_returns_the_tagged_mapping(self) -> None:
        body = (
            "before\n"
            "```yaml demir-kit\n"
            "demir_kit_version: '2'\n"
            "epic: 364\n"
            "risk: {level: medium}\n"
            "```\n"
            "after\n"
        )
        self.assertEqual(
            yamlish.parse_block(body, "demir-kit"),
            {"demir_kit_version": "2", "epic": 364, "risk": {"level": "medium"}},
        )
        self.assertEqual(yamlish.parse_block(body, "demir-kit-epic"), {})
        self.assertEqual(
            yamlish.parse_block(body, "demir-kit")["epic"], 364
        )

    def test_fallbacks_are_empty_instead_of_raising(self) -> None:
        self.assertEqual(yamlish.parse_block("", "demir-kit"), {})
        self.assertEqual(
            yamlish.parse_block("```yaml demir-kit\n[broken\n```", "demir-kit"),
            {},
        )
        self.assertEqual(
            yamlish.parse_block("```yaml demir-kit\n- a\n- b\n```", "demir-kit"),
            {},
        )

    def test_first_pass_modules_call_the_shared_parser(self) -> None:
        for name in self.PARSER_CALLERS:
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertIn("yamlish.parse_block(", text, name)
            self.assertNotRegex(text, self.INLINE_PARSER.pattern, name)

    def test_inline_yaml_block_parsers_match_the_d2_backlog(self) -> None:
        found = {
            path.name
            for path in sorted(SCRIPTS.glob("*.py"))
            if self.INLINE_PARSER.search(path.read_text(encoding="utf-8"))
        }
        self.assertFalse(found & set(self.PARSER_CALLERS))
        self.assertEqual(found, self.BACKLOG)


class RoutingTests(unittest.TestCase):
    def test_kit_signal_selects_pure_technical(self) -> None:
        path, signal = routing.detect_path(
            REGISTRY, "Agent visibility", "", {"surfaces": ["kit.docs"]}
        )
        self.assertEqual(path, "pure_technical")
        self.assertEqual(signal["id"], "kit_internal")

    def test_keyword_routing(self) -> None:
        path, signal = routing.detect_path(REGISTRY, "fix ci pipeline", "", {})
        self.assertEqual(path, "pure_technical")
        self.assertIsNone(signal)

    def test_narrow_path_wins_on_tie(self) -> None:
        path, _ = routing.detect_path(REGISTRY, "release landing page", "", {})
        self.assertEqual(path, "store_release")
        path, _ = routing.detect_path(REGISTRY, "chore release", "", {})
        self.assertEqual(path, "store_release")
        path, _ = routing.detect_path(REGISTRY, "ci landing", "", {})
        self.assertEqual(path, "landing_only")

    def test_entry_kind_fallback(self) -> None:
        path, signal, source = routing.detect_path_detail(
            REGISTRY, "unrelated title", "", {"surfaces": ["other"], "entry": {"kind": "chore"}}
        )
        self.assertEqual(path, "pure_technical")
        self.assertIsNone(signal)
        self.assertEqual(source, "entry")

    def test_no_stack_substring_hijack(self) -> None:
        path, _ = routing.detect_path(
            REGISTRY,
            "Add next action to brief",
            "",
            {"surfaces": ["other"], "entry": {"kind": "chore"}},
        )
        self.assertEqual(path, "pure_technical")

    def test_keyword_word_boundaries(self) -> None:
        path, _ = routing.detect_path(REGISTRY, "fix build", "", {})
        self.assertEqual(path, "pure_technical")
        path, _ = routing.detect_path(REGISTRY, "ui build", "", {})
        self.assertEqual(path, "ui_feature")

    def test_ios_signal_from_factory(self) -> None:
        data = {
            "surfaces": ["ios.app"],
            "factory": {
                "stacks": ["swiftui"],
                "distribution": ["app_store_connect"],
            },
        }
        path, signal = routing.detect_path(REGISTRY, "Onboarding", "", data)
        self.assertEqual(path, "full_product")
        self.assertEqual(signal["id"], "ios_app")
        agents = routing.resolve_agents(REGISTRY, path, signal)
        self.assertIn("marketing/stores", agents["active"])

    def test_android_signal_from_factory(self) -> None:
        data = {
            "surfaces": ["android.app"],
            "factory": {
                "stacks": ["flutter"],
                "distribution": ["play_console"],
            },
        }
        path, signal = routing.detect_path(REGISTRY, "Checkout", "", data)
        self.assertEqual(path, "full_product")
        self.assertEqual(signal["id"], "android_app")

    def test_experiment_extends_ui_feature(self) -> None:
        path, _ = routing.detect_path(REGISTRY, "feature flag rollout", "", {})
        self.assertEqual(path, "experiment")
        agents = routing.resolve_agents(REGISTRY, path)
        self.assertIn("growth/run", agents["active"])
        self.assertIn("designer", agents["active"])

    def test_kit_agents_and_inactive(self) -> None:
        agents = routing.resolve_agents(
            REGISTRY,
            "pure_technical",
            {"id": "kit_internal", "agents": {"required": ["analist", "developer"], "optional": ["devops"], "on_demand": ["architect"]}},
        )
        self.assertIn("analist", agents["active"])
        self.assertIn("developer", agents["active"])
        self.assertIn("architect", agents["on_demand"])
        self.assertNotIn("devops", agents["optional"])
        inactive = [item["id"] for item in routing.inactive_agents(REGISTRY, agents)]
        self.assertIn("designer", inactive)
        self.assertIn("marketing/stores", inactive)
        self.assertIn("growth/run", inactive)
        reasons = {
            item["id"]: item["reason"]
            for item in routing.inactive_agents(REGISTRY, agents)
        }
        self.assertIn("UI/UX", reasons["designer"])

    def test_next_action(self) -> None:
        self.assertIn("health-check", routing.next_action({"agent-approved"}, False))
        self.assertIn("resume", routing.next_action({"executing"}, False))
        self.assertIn("no-op", routing.next_action({"leaf-done"}, False))
        self.assertIn("epic kapandı", routing.next_action({"epic-done"}, True))

    def test_kit_prefix_vendored_product_with_one_git_root(self) -> None:
        # Regression: the vendored kit and the product share one git common
        # root, so the prefix must come from kit.config, not a path compare.
        with tempfile.TemporaryDirectory() as directory:
            product = Path(directory)
            (product / "kit.config.yaml").write_text(
                "kit:\n  root: demir-kit\n", encoding="utf-8"
            )
            kit_copy = product / "demir-kit"
            kit_copy.mkdir()
            (kit_copy / "VERSION").write_text("2.65.1\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(product)], check=True)
            self.assertEqual(
                routing.kit_prefix(kit_copy, product), "demir-kit/"
            )

    def test_kit_prefix_self_host_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text(
                'kit:\n  root: "."\n', encoding="utf-8"
            )
            self.assertEqual(routing.kit_prefix(root, root), "")

    def test_checkout_scoped_callers_use_checkout_root(self) -> None:
        wave = (SCRIPTS / "review_wave.py").read_text(encoding="utf-8")
        self.assertIn("worktree = str(routing.checkout_root(ROOT))", wave)
        report = (SCRIPTS / "report.py").read_text(encoding="utf-8")
        self.assertIn("CHECKOUT = routing.checkout_root(ROOT)", report)
        self.assertIn("cwd=CHECKOUT", report)
        self.assertIn('state_path = PROJECT / ".orchestration"', report)

    def test_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("kit:\n  root: demir-kit\n")
            self.assertEqual(routing.project_root(Path("/kit"), root), root)
            other = root / "other"
            other.mkdir()
            self.assertEqual(routing.project_root(Path("/kit"), other), Path("/kit"))

    def test_human_gates(self) -> None:
        self.assertIn("leaf QA (high)", routing.human_gates("high", False))
        self.assertIn("iki insan (critical)", routing.human_gates("critical", False))
        self.assertIn("epic kabulü", routing.human_gates("low", True))


class BriefTests(unittest.TestCase):
    def test_build_brief_for_leaf(self) -> None:
        data = brief.build_brief(
            REGISTRY, 13, "Agent visibility: brief.sh", seal(), {"agent-approved"}
        )
        self.assertEqual(data["state"], "leaf")
        self.assertEqual(data["path_id"], "pure_technical")
        self.assertEqual(data["signal"], "kit_internal")
        self.assertIn("developer", data["agents"]["active"])
        self.assertIn("delivery/agents/developer/ROLE.md", data["docs"])
        self.assertIn("health-check", data["next_action"])
        self.assertTrue(any(item["id"] == "designer" for item in data["inactive"]))

    def test_brief_product_prefix(self) -> None:
        data = brief.build_brief(
            REGISTRY, 35, "Product", seal(), {"agent-approved"}, prefix="demir-kit/"
        )
        self.assertIn("demir-kit/delivery/agents/developer/ROLE.md", data["docs"])

    def test_build_brief_for_epic(self) -> None:
        body = "```yaml demir-kit-epic\ndemir_kit_version: \"2\"\n```\n"
        data = brief.build_brief(REGISTRY, 12, "Epic 3", body, {"scope-confirmed"})
        self.assertEqual(data["state"], "epic")
        self.assertIn("epic kabulü", data["human_gates"])

    def test_build_brief_with_priorities(self) -> None:
        data = brief.build_brief(
            REGISTRY,
            13,
            "Brief",
            seal(),
            {"agent-approved"},
            priorities={
                "design_system": "docs/design/tokens.md",
                "architecture": ["docs/architecture/boundaries.md"],
                "quality_floor": "test + lint yeşil",
            },
        )
        self.assertEqual(
            data["priorities"]["design_system"], "docs/design/tokens.md"
        )
        rendered = brief.render(data)
        self.assertIn("project priorities (binding):", rendered)
        self.assertIn("design system: docs/design/tokens.md", rendered)
        comment = brief.comment_body(data)
        self.assertIn("priorities:", comment)

    def test_render_and_comment(self) -> None:
        data = brief.build_brief(REGISTRY, 13, "Brief", seal(), {"agent-approved"})
        rendered = brief.render(data)
        self.assertIn("path: pure_technical", rendered)
        self.assertIn("inactive:", rendered)
        comment = brief.comment_body(data)
        self.assertIn("## delivery_path", comment)
        self.assertIn("active_agents:", comment)

    def test_is_epic(self) -> None:
        self.assertTrue(routing.is_epic("```yaml demir-kit-epic\nx: 1\n```"))
        self.assertFalse(routing.is_epic(seal()))

    def test_is_epic_keeps_the_opening_fence_semantics(self) -> None:
        # Legacy behaviour: an epic block that is still being written (no
        # closing fence) is already an epic, not a leaf.
        self.assertTrue(routing.is_epic("```yaml demir-kit-epic\nx: 1\n"))
        self.assertTrue(routing.is_epic("```yaml demir-kit-epic\n"))

    def test_json_is_deterministic(self) -> None:
        first = json.dumps(
            brief.build_brief(REGISTRY, 13, "Brief", seal(), {"agent-approved"}),
            sort_keys=True,
        )
        second = json.dumps(
            brief.build_brief(REGISTRY, 13, "Brief", seal(), {"agent-approved"}),
            sort_keys=True,
        )
        self.assertEqual(first, second)

    def test_existing_delivery_path_paginates(self) -> None:
        pages = [[{"body": "x"}] * 100, [{"body": "## delivery_path"}]]
        calls = {"page": 0}

        def fetch(args):
            index = calls["page"]
            calls["page"] += 1
            return json.dumps(pages[index])

        self.assertTrue(brief.existing_delivery_path("o/r", 1, fetch=fetch))
        self.assertEqual(calls["page"], 2)

    def test_existing_delivery_path_false(self) -> None:
        def fetch(args):
            return json.dumps([{"body": "x"}])

        self.assertFalse(brief.existing_delivery_path("o/r", 1, fetch=fetch))

    def test_has_delivery_path(self) -> None:
        self.assertTrue(
            brief.has_delivery_path([{"body": "## delivery_path\n"}])
        )
        self.assertFalse(brief.has_delivery_path([{"body": "hello"}]))


if __name__ == "__main__":
    unittest.main()
