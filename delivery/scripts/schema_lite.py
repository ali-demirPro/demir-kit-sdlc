"""Minimal JSON Schema subset shared by doctor and cp_close."""

from __future__ import annotations

import re


def _json_type(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate_schema(instance, schema, path: str = "$") -> list[str]:
    """Minimal JSON Schema subset used by the v2 leaf schema."""
    if not isinstance(schema, dict):
        return []
    errors: list[str] = []

    if "type" in schema and not _json_type(instance, schema["type"]):
        return [f"{path}: '{schema['type']}' bekleniyor"]

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: {schema['const']!r} bekleniyor")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} enum dışında")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: en az {schema['minLength']} karakter")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: '{schema['pattern']}' desenine uymuyor")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: en az {schema['minimum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: en az {schema['minItems']} öğe")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: en fazla {schema['maxItems']} öğe")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors += validate_schema(item, schema["items"], f"{path}[{index}]")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: eksik")
        properties = schema.get("properties") or {}
        for key, value in instance.items():
            if key in properties:
                errors += validate_schema(value, properties[key], f"{path}.{key}")
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.append(f"{path}.{key}: izin verilmeyen alan")
            elif isinstance(additional, dict):
                errors += validate_schema(value, additional, f"{path}.{key}")

    if "allOf" in schema:
        for sub in schema["allOf"]:
            errors += validate_schema(instance, sub, path)

    if isinstance(schema.get("if"), dict):
        if not validate_schema(instance, schema["if"], path):
            then = schema.get("then")
            if isinstance(then, dict):
                errors += validate_schema(instance, then, path)

    return errors
