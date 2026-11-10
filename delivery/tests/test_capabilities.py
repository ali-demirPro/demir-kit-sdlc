"""Tests for the capability registry and role matrix."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("capabilities", SCRIPTS / "capabilities.py")
capabilities = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(capabilities)

doctor_spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(doctor_spec)
assert doctor_spec.loader is not None
doctor_spec.loader.exec_module(doctor)

REGISTRY = capabilities.load_yaml(capabilities.REGISTRY)
MATRIX = capabilities.load_yaml(capabilities.MATRIX)
CAP_SCHEMA = json.loads(
    (ROOT / "delivery" / "schemas" / "capability.schema.json").read_text()
)
MATRIX_SCHEMA = json.loads(
    (ROOT / "delivery" / "schemas" / "role-matrix.schema.json").read_text()
)
ROLES = set(
    (capabilities.load_yaml(ROOT / "delivery" / "registry.yaml").get("role_order_default") or [])
) | {"orchestrator"}
PACKS = {
    path.name
    for path in (ROOT / "delivery" / "packs").iterdir()
    if path.is_dir()
}


class CapabilityTests(unittest.TestCase):
    def test_registry_schema_and_references(self) -> None:
        self.assertEqual(doctor.validate_schema(REGISTRY, CAP_SCHEMA), [])
        self.assertEqual(
            capabilities.validate_references(REGISTRY, MATRIX, ROLES, PACKS, ROLES),
            [],
        )

    def test_role_matrix_schema(self) -> None:
        self.assertEqual(doctor.validate_schema(MATRIX, MATRIX_SCHEMA), [])

    def test_unknown_role_in_capability(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["roles"]["unknown"] = "expert"
        errors = capabilities.validate_references(
            registry, MATRIX, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("bilinmeyen rol" in item for item in errors))

    def test_unknown_pack(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["packs"].append("missing-pack")
        errors = capabilities.validate_references(
            registry, MATRIX, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("bilinmeyen pack" in item for item in errors))

    def test_unknown_capability_in_matrix(self) -> None:
        matrix = copy.deepcopy(MATRIX)
        matrix["roles"]["architect"]["capabilities"]["platform.unknown"] = "expert"
        errors = capabilities.validate_references(
            REGISTRY, matrix, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("bilinmeyen capability" in item for item in errors))

    def test_invalid_level(self) -> None:
        matrix = copy.deepcopy(MATRIX)
        matrix["roles"]["architect"]["capabilities"]["platform.web"] = "ninja"
        errors = capabilities.validate_references(
            REGISTRY, matrix, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("geçersiz seviye" in item for item in errors))

    def test_capability_requires_roles(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["roles"] = {}
        errors = capabilities.validate_references(
            registry, MATRIX, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("roles boş" in item for item in errors))

    def test_capability_requires_match(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["match"] = {}
        errors = capabilities.validate_references(
            registry, MATRIX, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("match sinyali boş" in item for item in errors))

    def test_matrix_missing_role(self) -> None:
        matrix = copy.deepcopy(MATRIX)
        del matrix["roles"]["designer"]
        errors = capabilities.validate_references(
            REGISTRY, matrix, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("eksik rol: designer" in item for item in errors))

    def test_agent_authority_rejected(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["roles"]["developer"] = "authority"
        errors = capabilities.validate_references(
            registry, MATRIX, ROLES, PACKS, ROLES
        )
        self.assertTrue(any("authority olamaz" in item for item in errors))

    def test_effective_level_is_monotonic(self) -> None:
        self.assertEqual(
            capabilities.effective_level("aware", "high", REGISTRY), "expert"
        )
        self.assertEqual(
            capabilities.effective_level("expert", "low", REGISTRY), "expert"
        )

    def test_matrix_render_contains_roles(self) -> None:
        text = capabilities.render_matrix(REGISTRY, MATRIX)
        self.assertIn("architect", text)
        self.assertIn("platform.web"[:0] or "web", text)

    def test_every_capability_has_path_globs(self) -> None:
        for cap_id, capability in REGISTRY["capabilities"].items():
            self.assertTrue(capability.get("paths"), cap_id)

    def test_missing_paths_rejected_by_schema(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        del registry["capabilities"]["platform.web"]["paths"]
        errors = doctor.validate_schema(registry, CAP_SCHEMA)
        self.assertTrue(any(".paths: eksik" in item for item in errors), errors)

    def test_empty_paths_rejected_by_schema(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["paths"] = []
        errors = doctor.validate_schema(registry, CAP_SCHEMA)
        self.assertTrue(any("en az 1 öğe" in item for item in errors), errors)

    def test_unknown_surface_rejected(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["capabilities"]["platform.web"]["match"]["surfaces"] = ["unknown.surface"]
        schema_errors = doctor.validate_schema(registry, CAP_SCHEMA)
        self.assertTrue(
            any("enum dışında" in item for item in schema_errors), schema_errors
        )
        errors = capabilities.validate_references(registry, MATRIX, ROLES, PACKS, ROLES)
        self.assertTrue(any("bilinmeyen surface" in item for item in errors), errors)

    def test_schema_surface_enum_matches_registry(self) -> None:
        items = CAP_SCHEMA["properties"]["capabilities"]["additionalProperties"][
            "properties"
        ]["match"]["properties"]["surfaces"]["items"]
        enum = items["enum"]
        self.assertEqual(len(enum), len(set(enum)))
        self.assertEqual(set(enum), set(REGISTRY["surfaces"]))

    def test_surface_without_paths_rejected(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["surfaces"]["kit.docs"] = {"label": "Kit dokümanı"}
        schema_errors = doctor.validate_schema(registry, CAP_SCHEMA)
        self.assertTrue(any(".paths: eksik" in item for item in schema_errors), schema_errors)
        reference_errors = capabilities.validate_references(
            registry, MATRIX, ROLES, PACKS, ROLES
        )
        self.assertTrue(
            any("paths glob listesi boş" in item for item in reference_errors),
            reference_errors,
        )

    def test_capability_surfaces_are_declared(self) -> None:
        declared = set(REGISTRY["surfaces"])
        used = {
            str(surface)
            for capability in REGISTRY["capabilities"].values()
            for surface in (capability.get("match") or {}).get("surfaces") or []
        }
        self.assertEqual(used - declared, set())
        self.assertIn("kit.docs", declared)


if __name__ == "__main__":
    unittest.main()
