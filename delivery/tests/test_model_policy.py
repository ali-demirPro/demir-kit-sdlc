"""Tests for model selection policy."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "model_policy", SCRIPTS / "model_policy.py"
)
model_policy = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(model_policy)


def project_with(config: str) -> Path:
    directory = tempfile.mkdtemp()
    Path(directory, "kit.config.yaml").write_text(config, encoding="utf-8")
    return Path(directory)


class ModelPolicyTests(unittest.TestCase):
    def test_default_passes_nothing(self) -> None:
        project = project_with("orca: {}\n")
        self.assertEqual(model_policy.role_launch(project, "developer"), {})

    def test_inherit_session_model(self) -> None:
        project = project_with("orca: {inherit_session_model: true}\n")
        with patch.object(
            model_policy, "session_model", return_value="provider/model"
        ):
            launch = model_policy.role_launch(project, "developer")
        self.assertEqual(launch, {"model": "provider/model"})

    def test_role_defaults_need_allow(self) -> None:
        project = project_with(
            "orca:\n  role_defaults:\n    developer: {model: cheap/model, effort: low}\n"
        )
        self.assertEqual(model_policy.role_launch(project, "developer"), {})

    def test_role_defaults_with_allow(self) -> None:
        project = project_with(
            "orca:\n  allow_model_override: true\n  role_defaults:\n"
            "    developer: {model: cheap/model, effort: low, agent: opencode2}\n"
        )
        self.assertEqual(
            model_policy.role_launch(project, "developer"),
            {"model": "cheap/model", "effort": "low", "agent": "opencode2"},
        )

    def test_agent_does_not_need_allow(self) -> None:
        project = project_with(
            "orca:\n  role_defaults:\n    developer: {agent: opencode2}\n"
        )
        self.assertEqual(
            model_policy.role_launch(project, "developer"), {"agent": "opencode2"}
        )


class DoctorModelPolicyTests(unittest.TestCase):
    def test_override_without_allow_errors(self) -> None:
        import doctor

        project = project_with(
            "orca:\n  role_defaults:\n    developer: {model: m}\n"
        )
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_model_policy(project)
        self.assertTrue(any("allow_model_override" in item for item in doctor.ERRORS))

    def test_override_with_allow_passes(self) -> None:
        import doctor

        project = project_with(
            "orca:\n  allow_model_override: true\n  role_defaults:\n"
            "    developer: {model: m}\n"
        )
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_model_policy(project)
        self.assertEqual(doctor.ERRORS, [])

    def test_effort_warns(self) -> None:
        import doctor

        project = project_with(
            "orca:\n  allow_model_override: true\n  role_defaults:\n"
            "    developer: {model: m, effort: high}\n"
        )
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_model_policy(project)
        self.assertTrue(any("effort" in item for item in doctor.WARNS))


if __name__ == "__main__":
    unittest.main()
