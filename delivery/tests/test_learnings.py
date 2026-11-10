"""Tests for fleet learning federation (self-improvement lane)."""

from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


SKILL_TEXT = (
    "---\nname: alpha\ndescription: >-\n  Alpha skill fixture. Use when testing.\n"
    "---\n\n# alpha\n\n## Steps\n\nDo it.\n\n## Done when\n\nOk.\n"
)


class ProposalFixture(unittest.TestCase):
    """Ortak kurulum: bir canlı skill, registry, VERSION ve CHANGELOG."""

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
        skill = root / "skills" / "alpha" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(SKILL_TEXT, encoding="utf-8")
        return root

    def learning(self, number: int = 1) -> dict:
        return record(
            "o/a", number, f"skill notu {number}: `skills/alpha/SKILL.md` güncelle"
        )


class ProposeTests(ProposalFixture):
    """T-1/T-2: taslak + diff üretilir, canlı skill değişmez, sınır uygulanır."""

    def test_propose_writes_draft_and_diff_without_touching_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            before = live.read_text(encoding="utf-8")

            result = learnings.propose_one(root, self.learning())

            self.assertEqual(result["status"], "pending")
            self.assertEqual(
                result["draft"], f"skills/.drafts/{result['id']}/SKILL.md"
            )
            draft_path = root / result["draft"]
            self.assertTrue(draft_path.is_file())
            draft = draft_path.read_text(encoding="utf-8")
            self.assertIn("## Öğrenimler", draft)
            self.assertIn("[öğrenim o/a#1]", draft)
            self.assertLess(draft.index("## Öğrenimler"), draft.index("## Done when"))
            body = (root / result["body"]).read_text(encoding="utf-8")
            self.assertIn("## Skill önerisi — o/a#1", body)
            self.assertIn("--- skills/alpha/SKILL.md", body)
            self.assertIn("+## Öğrenimler", body)
            self.assertIn("--accept", body)
            self.assertEqual(live.read_text(encoding="utf-8"), before)

    def test_sixth_pending_proposal_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            for number in range(1, 6):
                result = learnings.propose_one(root, self.learning(number))
                self.assertEqual(result["status"], "pending", result)
            self.assertEqual(
                len(learnings.pending_proposals(root, "developer")), 5
            )

            refused = learnings.propose_one(root, self.learning(6))

            self.assertEqual(refused["status"], "refused")
            record_path = root / ".kit" / "proposals" / f"{refused['id']}.json"
            self.assertTrue(record_path.is_file())
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "refused")
            self.assertFalse(
                (root / "skills" / ".drafts" / refused["id"] / "SKILL.md").exists()
            )

    def test_non_skill_learning_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            item = record("o/a", 7, "yeni risk glob: `**/crypto/**`")
            result = learnings.propose_one(root, item)
            self.assertEqual(result["status"], "skipped")
            self.assertIn("skill hedefi yok", result["note"])


class ReproposeTests(ProposalFixture):
    """Terminal/bayat kayıt yeni kimlikle yeniden önerilir; pending kilitler."""

    def record_path(self, root: Path, ident: str) -> Path:
        return root / ".kit" / "proposals" / f"{ident}.json"

    def test_rejected_proposal_reopens_with_new_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            item = self.learning()
            first = learnings.propose_one(root, item)
            self.assertEqual(learnings.reject_proposal(root, first["id"])["status"], "rejected")

            second = learnings.propose_one(root, item)

            self.assertEqual(second["status"], "pending")
            self.assertEqual(second["id"], f"{first['id']}-2")
            self.assertTrue((root / second["draft"]).is_file())
            old = json.loads(self.record_path(root, first["id"]).read_text(encoding="utf-8"))
            self.assertEqual(old["status"], "rejected")
            self.assertEqual(learnings.proposal_for(root, item)["id"], second["id"])

            # Gerçekten bekleyen kayıt yeniden açılmaz, aynı kimlik döner.
            again = learnings.propose_one(root, item)
            self.assertEqual((again["status"], again["id"]), ("pending", second["id"]))

    def test_accepted_proposal_reopens_with_new_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            item = self.learning()
            first = learnings.propose_one(root, item)
            self.assertEqual(
                learnings.accept_proposal(root, first["id"])["status"], "accepted"
            )
            # İnsan onayı geri alır (canlı skill eski hâline döner); yeniden öneri açılmalı.
            self.assertEqual(learnings.revert_skill(root, "alpha")["status"], "reverted")

            second = learnings.propose_one(root, item)

            self.assertEqual(second["status"], "pending")
            self.assertEqual(second["id"], f"{first['id']}-2")
            old = json.loads(self.record_path(root, first["id"]).read_text(encoding="utf-8"))
            self.assertEqual(old["status"], "accepted")
            self.assertEqual(
                json.loads(self.record_path(root, second["id"]).read_text(encoding="utf-8"))[
                    "revision"
                ],
                2,
            )

    def test_stale_pending_proposal_is_superseded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            item = self.learning()
            first = learnings.propose_one(root, item)
            live.write_text(
                live.read_text(encoding="utf-8") + "\nElle değişiklik.\n",
                encoding="utf-8",
            )

            second = learnings.propose_one(root, item)

            self.assertEqual(second["status"], "pending")
            self.assertEqual(second["id"], f"{first['id']}-2")
            self.assertEqual(
                json.loads(self.record_path(root, first["id"]).read_text(encoding="utf-8"))[
                    "status"
                ],
                "stale",
            )
            pending = learnings.pending_proposals(root)
            self.assertEqual([record["id"] for record in pending], [second["id"]])
            # Bayat kayıt artık onaylanamaz; yeni kayıt onaylanır.
            self.assertEqual(
                learnings.accept_proposal(root, first["id"])["status"], "stale"
            )
            self.assertEqual(
                learnings.accept_proposal(root, second["id"])["status"], "accepted"
            )

    def test_legacy_draft_is_read_by_accept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            item = self.learning()
            slug = learnings.proposal_slug(item)
            legacy = root / ".kit" / "proposals" / f"{slug}.draft.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                learnings.skill_note_applied(live.read_text(encoding="utf-8"), item) or "",
                encoding="utf-8",
            )
            learnings.write_record(
                root / ".kit" / "proposals" / f"{slug}.json",
                {
                    "demir_kit_version": "2",
                    "id": slug,
                    "issue_ref": item["id"],
                    "class": item.get("class"),
                    "kind": item["proposed_change"]["kind"],
                    "target": "skills/alpha/SKILL.md",
                    "draft": f".kit/proposals/{slug}.draft.md",
                    "base_sha256": hashlib.sha256(
                        live.read_text(encoding="utf-8").encode("utf-8")
                    ).hexdigest(),
                    "agent": "developer",
                    "created": "2026-01-01",
                    "status": "pending",
                },
            )

            result = learnings.accept_proposal(root, slug)

            self.assertEqual(result["status"], "accepted")
            self.assertIn("## Öğrenimler", live.read_text(encoding="utf-8"))
            self.assertFalse(legacy.exists())

    def test_missing_draft_reports_clear_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            item = self.learning()
            slug = learnings.proposal_slug(item)
            learnings.write_record(
                root / ".kit" / "proposals" / f"{slug}.json",
                {
                    "demir_kit_version": "2",
                    "id": slug,
                    "issue_ref": item["id"],
                    "target": "skills/alpha/SKILL.md",
                    "agent": "developer",
                    "created": "2026-01-01",
                    "status": "pending",
                },
            )

            result = learnings.accept_proposal(root, slug)

            self.assertEqual(result["status"], "missing")
            self.assertIn("taslak yok", result["note"])
            self.assertIn(".kit/proposals/", result["note"])
            self.assertIn("skills/.drafts/", result["note"])
            self.assertIn("yeniden --propose", result["note"])


class ProposeCliTests(ProposalFixture):
    """CLI: ret sonrası `--propose` yeni kimlik üretir, pending kayıt kilitler."""

    def run_cli(self, root: Path, *argv: str) -> str:
        original_digest = learnings.DIGEST
        original_argv = sys.argv
        learnings.DIGEST = root / ".orchestration" / "learnings" / "digest.json"
        sys.argv = ["learnings.py", "--project", str(root), *argv]
        out = io.StringIO()
        try:
            with redirect_stdout(out):
                self.assertEqual(learnings.main(), 0)
        finally:
            learnings.DIGEST = original_digest
            sys.argv = original_argv
        return out.getvalue()

    def proposal_ids(self, root: Path) -> list[str]:
        base = root / ".kit" / "proposals"
        return sorted(path.stem for path in base.glob("*.json"))

    def test_reject_then_propose_cli_reopens_with_new_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            item = self.learning()
            item["status"] = "candidate"
            digest = root / ".orchestration" / "learnings" / "digest.json"
            digest.parent.mkdir(parents=True)
            digest.write_text(json.dumps([item]), encoding="utf-8")

            self.assertIn("pending", self.run_cli(root, "--propose"))
            first_id = self.proposal_ids(root)[0]
            self.assertIn("rejected", self.run_cli(root, "--reject", first_id))

            output = self.run_cli(root, "--propose")

            ids = self.proposal_ids(root)
            self.assertEqual(ids, sorted([first_id, f"{first_id}-2"]))
            self.assertIn(f"{first_id}-2", output)
            self.assertIn("pending", output)
            old = json.loads(
                (root / ".kit" / "proposals" / f"{first_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(old["status"], "rejected")


class AcceptRevertTests(ProposalFixture):
    """T-3: onayda önceki sürüm saklanır, geri dönüş yazar, ret taslağı siler."""

    def test_accept_archives_previous_and_revert_restores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            before = live.read_text(encoding="utf-8")
            proposal = learnings.propose_one(root, self.learning())
            draft_path = root / proposal["draft"]

            accepted = learnings.accept_proposal(root, proposal["id"])

            self.assertEqual(accepted["status"], "accepted")
            self.assertIn("## Öğrenimler", live.read_text(encoding="utf-8"))
            self.assertFalse(draft_path.exists())
            history = sorted((root / ".kit" / "skill-history" / "alpha").glob("*.md"))
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].read_text(encoding="utf-8"), before)
            record = json.loads(
                (root / ".kit" / "proposals" / f"{proposal['id']}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(record["status"], "accepted")
            self.assertNotIn("draft", record)

            reverted = learnings.revert_skill(root, "alpha")

            self.assertEqual(reverted["status"], "reverted")
            self.assertEqual(live.read_text(encoding="utf-8"), before)

    def test_reject_deletes_draft_and_keeps_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            before = live.read_text(encoding="utf-8")
            proposal = learnings.propose_one(root, self.learning())
            record_path, draft_path, body_path = learnings.proposal_files(
                root, proposal["id"]
            )
            for path in (record_path, draft_path, body_path):
                self.assertTrue(path.is_file())

            result = learnings.reject_proposal(root, proposal["id"])

            self.assertEqual(result["status"], "rejected")
            self.assertFalse(draft_path.exists())
            self.assertFalse(body_path.exists())
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "rejected")
            self.assertNotIn("draft", record)
            self.assertNotIn("body", record)
            self.assertEqual(live.read_text(encoding="utf-8"), before)
            self.assertEqual(learnings.pending_proposals(root), [])

    def test_accept_rejects_stale_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            proposal = learnings.propose_one(root, self.learning())
            live.write_text(
                live.read_text(encoding="utf-8") + "\nElle değişiklik.\n",
                encoding="utf-8",
            )
            changed = live.read_text(encoding="utf-8")

            result = learnings.accept_proposal(root, proposal["id"])

            self.assertEqual(result["status"], "stale")
            self.assertIn("bayat", result["note"])
            self.assertEqual(live.read_text(encoding="utf-8"), changed)
            self.assertFalse((root / ".kit" / "skill-history" / "alpha").exists())


class ApprovalBoundaryTests(ProposalFixture):
    """Onay sınırı: ret/limit kaydı `--apply` ile canlıya yazılmaz."""

    def digest(self, root: Path, item: dict) -> Path:
        path = root / "digest.json"
        path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
        return path

    def test_apply_skips_rejected_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            before = live.read_text(encoding="utf-8")
            item = self.learning()
            item["status"] = "candidate"
            proposal = learnings.propose_one(root, item)
            self.assertEqual(
                learnings.reject_proposal(root, proposal["id"])["status"], "rejected"
            )

            actions = learnings.apply_all(root, self.digest(root, item))

            self.assertTrue(
                any(
                    line.startswith("rejected:") and "reddedildi" in line
                    for line in actions
                ),
                actions,
            )
            self.assertEqual(live.read_text(encoding="utf-8"), before)
            self.assertEqual((root / "VERSION").read_text(encoding="utf-8"), "2.0.0\n")

    def test_apply_skips_refused_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            for number in range(1, 6):
                self.assertEqual(
                    learnings.propose_one(root, self.learning(number))["status"],
                    "pending",
                )
            item = self.learning(6)
            item["status"] = "candidate"
            refused = learnings.propose_one(root, item)
            self.assertEqual(refused["status"], "refused")
            before = live.read_text(encoding="utf-8")

            actions = learnings.apply_all(root, self.digest(root, item))

            self.assertTrue(
                any(
                    line.startswith("refused:") and "reddedildi" in line
                    for line in actions
                ),
                actions,
            )
            self.assertEqual(live.read_text(encoding="utf-8"), before)

    def test_apply_never_reapplies_accepted_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            before = live.read_text(encoding="utf-8")
            item = self.learning()
            item["status"] = "candidate"
            proposal = learnings.propose_one(root, item)
            self.assertEqual(
                learnings.accept_proposal(root, proposal["id"])["status"], "accepted"
            )
            # Onaydan sonra insan notu geri almış olsun: --apply yeniden yazmamalı.
            live.write_text(before, encoding="utf-8")

            actions = learnings.apply_all(root, self.digest(root, item))

            self.assertTrue(
                any(
                    line.startswith("accepted:") and "onaylandı" in line
                    for line in actions
                ),
                actions,
            )
            self.assertEqual(live.read_text(encoding="utf-8"), before)


class ApplyPreservedTests(ProposalFixture):
    """T-4: `--apply` davranışı korunur; bekleyen taslak canlıya yazılmaz."""

    def test_apply_all_still_applies_auto_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            item = record("o/a", 9, "yeni risk glob: `**/crypto/**`")
            item["status"] = "candidate"
            digest = root / "digest.json"
            digest.write_text(json.dumps([item]), encoding="utf-8")

            actions = learnings.apply_all(root, digest)

            registry = (root / "delivery" / "registry.yaml").read_text(encoding="utf-8")
            self.assertEqual(registry.count("**/crypto/**"), 1)
            self.assertTrue(
                any(line.startswith("version: 2.0.0 → 2.0.1") for line in actions),
                actions,
            )

    def test_pending_proposal_keeps_live_skill_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory)
            live = root / "skills" / "alpha" / "SKILL.md"
            before = live.read_text(encoding="utf-8")
            item = self.learning()
            item["status"] = "candidate"
            self.assertEqual(
                learnings.propose_one(root, item)["status"], "pending"
            )
            digest = root / "digest.json"
            digest.write_text(json.dumps([item]), encoding="utf-8")

            actions = learnings.apply_all(root, digest)

            self.assertTrue(any(line.startswith("pending:") for line in actions), actions)
            self.assertEqual(live.read_text(encoding="utf-8"), before)
            self.assertEqual((root / "VERSION").read_text(encoding="utf-8"), "2.0.0\n")


class ContractReferenceTests(unittest.TestCase):
    """T-2: self-improvement lane atfı I22'yi, I13 ise rebase'i anlatır."""

    def contract_rows(self, anchor: str) -> list[str]:
        text = (ROOT / "delivery" / "CONTRACT.md").read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line.startswith(f"| {anchor} |")]

    def test_learnings_docstring_cites_i22_not_i13(self) -> None:
        docstring = learnings.__doc__ or ""
        self.assertIn("I22", docstring)
        self.assertNotIn("I13 kapsamı", docstring)

    def test_contract_i22_is_epic_done_human_acceptance(self) -> None:
        rows = self.contract_rows("I22")
        self.assertEqual(len(rows), 1)
        self.assertIn("epic-done", rows[0])
        self.assertIn("demir-kit-accept", rows[0])

    def test_contract_i13_stays_rebase_only(self) -> None:
        rows = self.contract_rows("I13")
        self.assertEqual(len(rows), 1)
        self.assertIn("rebase", rows[0])
        self.assertNotIn("kapsam", rows[0])