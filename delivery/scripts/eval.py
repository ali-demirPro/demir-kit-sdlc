#!/usr/bin/env python3
"""Validate and enforce capability eval scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_lite import validate_schema

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "delivery" / "agents"
FINDINGS = ROOT / "delivery" / "findings"
FINDING_SCHEMA = ROOT / "delivery" / "schemas" / "finding.schema.json"
CASE_SCHEMA = ROOT / "delivery" / "schemas" / "eval_case.schema.json"
REVISION_LOG = ROOT / ".kit" / "eval-revisions.jsonl"
FINDING_SUFFIXES = (".finding.yaml", ".finding.yml", ".finding.json")
CASE_REQUIRED = ("id", "intent", "criteria", "targets")
MIN_ROWS = 10
RESULT_VALUES = {"pass", "fail", "skip"}
VERIFY_STATES = ("yes", "no", "unknown")


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_finding_schema() -> dict:
    try:
        data = json.loads(FINDING_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_case_schema() -> dict:
    try:
        data = json.loads(CASE_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


class CaseError(ValueError):
    """Raised when a committed case cannot be parsed."""


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """Return ``(frontmatter, body, error)`` without changing the legacy table."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, None
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            raw = "\n".join(lines[1:index])
            try:
                data = yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                return None, "", f"frontmatter ayrıştırılamadı: {exc}"
            if not isinstance(data, dict):
                return None, "", "frontmatter mapping değil"
            return data, "\n".join(lines[index + 1 :]), None
    return None, "", "frontmatter kapanmadı"


def has_frontmatter(path: Path) -> bool:
    try:
        return path.read_text(encoding="utf-8").lstrip("\ufeff").startswith("---")
    except OSError:
        return False


def parse_case(path: Path) -> dict:
    """Parse one committed case; the body is the agent prompt."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CaseError(f"okunamadı: {exc}") from exc
    raw = raw.lstrip("\ufeff")
    frontmatter, body, error = split_frontmatter(raw)
    if error:
        raise CaseError(error)
    if frontmatter is None:
        raise CaseError("frontmatter yok")
    case = dict(frontmatter)
    case["body"] = body.strip()
    case["path"] = str(path)
    case["revision"] = content_sha256(raw.encode("utf-8"))
    return case


def content_sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def path_sha256(path: Path) -> str:
    """Hash a file's bytes, or a directory's sorted relative paths and bytes."""
    if path.is_dir():
        digest = hashlib.sha256()
        for item in sorted(path.rglob("*")):
            if not item.is_file():
                continue
            digest.update(str(item.relative_to(path)).encode("utf-8") + b"\0")
            digest.update(item.read_bytes())
            digest.update(b"\0")
        return "sha256:" + digest.hexdigest()
    return content_sha256(path.read_bytes())


def resolve_input(entry: str, case_dir: Path, root: Path = ROOT) -> Path | None:
    """Resolve a case input relative to the case, then the kit root."""
    candidate = Path(entry).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for base in (case_dir, root):
        resolved = base / candidate
        if resolved.exists():
            return resolved
    return None


def check_case_file(path: Path, schema: dict | None = None) -> list[str]:
    """Validate one committed case; missing required fields are failures."""
    if not path.is_file():
        return [f"case dosyası yok: {path}"]
    try:
        case = parse_case(path)
    except CaseError as exc:
        return [f"{path}: {exc}"]
    schema = load_case_schema() if schema is None else schema
    if not schema:
        return [f"case şeması yok: {CASE_SCHEMA}"]
    record = {key: value for key, value in case.items() if key not in {"body", "path", "revision"}}
    messages = validate_schema(record, schema, "$")
    return [f"{path}: {message}" for message in messages]


def load_finding_record(path: Path) -> tuple[dict, list[str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, [f"{path}: okunamadı ({exc})"]
    try:
        data = json.loads(raw) if path.suffix == ".json" else yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError):
        return {}, [f"{path}: ayrıştırılamadı"]
    if not isinstance(data, dict):
        return {}, [f"{path}: kök mapping değil"]
    return data, []


def finding_files(directory: Path | None = None) -> list[Path]:
    base = FINDINGS if directory is None else directory
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.iterdir()
        if path.is_file() and path.name.endswith(FINDING_SUFFIXES)
    )


def check_finding_file(path: Path, schema: dict | None = None) -> list[str]:
    """Validate one finding record; UNKNOWN is a result, never a failure."""
    if not path.is_file():
        return [f"bulgu dosyası yok: {path}"]
    record, errors = load_finding_record(path)
    if errors:
        return errors
    schema = load_finding_schema() if schema is None else schema
    if not schema:
        return [f"bulgu şeması yok: {FINDING_SCHEMA}"]
    messages = validate_schema(record, schema, "$")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        messages.append("$.evidence: kanıt referansı yok")
    return [f"{path}: {message}" for message in messages]


def check_findings(directory: Path | None = None) -> list[str]:
    schema = load_finding_schema()
    errors: list[str] = []
    for path in finding_files(directory):
        errors.extend(check_finding_file(path, schema))
    return errors


def parse_eval(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in {"id", "senaryo"}:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) < 4:
            continue
        rows.append(
            {
                "id": cells[0],
                "scenario": cells[1],
                "expected": cells[2],
                "fail": cells[3],
            }
        )
    return rows


def check_eval_file(path: Path, minimum: int = MIN_ROWS) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"eval dosyası yok: {path}"]
    if has_frontmatter(path):
        return check_case_file(path)
    rows = parse_eval(path)
    if len(rows) < minimum:
        errors.append(f"{path}: en az {minimum} senaryo (şu an {len(rows)})")
    seen: set[str] = set()
    for row in rows:
        if not row["id"]:
            errors.append(f"{path}: boş senaryo ID")
        elif row["id"] in seen:
            errors.append(f"{path}: tekrarlı senaryo ID {row['id']}")
        seen.add(row["id"])
        for key in ("scenario", "expected", "fail"):
            if not row[key]:
                errors.append(f"{path}: {row['id']} için {key} boş")
    return errors


def _check(state: str, check_id: str, detail: str) -> dict:
    return {"id": check_id, "state": state, "detail": detail}


def _target_state(entry: str, case_dir: Path, root: Path) -> tuple[str, str]:
    if not isinstance(entry, str) or not entry.strip():
        return "no", "hedef boş"
    if any(marker in entry for marker in ("*", "?", "[", "]", "${{", "://")):
        return "unknown", "hedef çözümlenemedi (glob/değişken/URL)"
    candidate = Path(entry).expanduser()
    if candidate.is_absolute():
        return ("yes", "hedef var") if candidate.exists() else ("no", "hedef yok")
    for base in (root, case_dir):
        if (base / candidate).exists():
            return "yes", "hedef var"
    return "no", "hedef yok"


def verify_case(path: Path, root: Path = ROOT) -> dict:
    """Static yes/no/unknown checklist; exit 1 is reserved for a definite no."""
    checks: list[dict] = []
    if not path.is_file():
        checks.append(_check("no", "case.file", f"case dosyası yok: {path}"))
        return _verification(path, checks)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        checks.append(_check("no", "case.file", f"okunamadı: {exc}"))
        return _verification(path, checks)
    frontmatter, _body, error = split_frontmatter(raw)
    if error:
        checks.append(_check("no", "case.frontmatter", error))
        return _verification(path, checks)
    if frontmatter is None:
        checks.append(_check("no", "case.frontmatter", "frontmatter yok"))
        return _verification(path, checks)

    checks.append(_check("yes", "case.frontmatter", "frontmatter ayrıştırıldı"))
    for field in CASE_REQUIRED:
        value = frontmatter.get(field)
        present = value not in (None, "", [])
        checks.append(
            _check(
                "yes" if present else "no",
                f"case.{field}",
                f"{field} var" if present else f"{field} eksik",
            )
        )

    schema = load_case_schema()
    if not schema:
        checks.append(_check("unknown", "case.schema", "case şeması yok"))
    elif all(frontmatter.get(field) not in (None, "", []) for field in CASE_REQUIRED):
        errors = validate_schema(frontmatter, schema, "$")
        checks.append(
            _check(
                "no" if errors else "yes",
                "case.schema",
                "; ".join(errors) if errors else "şema uygun",
            )
        )

    targets = frontmatter.get("targets")
    if isinstance(targets, list):
        for index, entry in enumerate(targets):
            state, detail = _target_state(entry, path.parent, root)
            checks.append(_check(state, f"case.target.{index}", f"{entry}: {detail}"))

    inputs = frontmatter.get("inputs")
    if isinstance(inputs, list):
        for index, entry in enumerate(inputs):
            if not isinstance(entry, str) or not entry.strip():
                checks.append(_check("no", f"case.input.{index}", "girdi boş"))
            elif resolve_input(entry, path.parent, root) is None:
                checks.append(_check("no", f"case.input.{index}", f"{entry}: girdi yok"))
            else:
                checks.append(_check("yes", f"case.input.{index}", f"{entry}: girdi var"))

    tools = frontmatter.get("tools")
    if isinstance(tools, list):
        for index, entry in enumerate(tools):
            if not isinstance(entry, str) or not entry.strip():
                checks.append(_check("no", f"case.tool.{index}", "araç boş"))
            else:
                checks.append(
                    _check(
                        "unknown",
                        f"case.tool.{index}",
                        f"{entry}: araç varlığı statik olarak doğrulanamadı",
                    )
                )
    return _verification(path, checks)


def _verification(path: Path, checks: list[dict]) -> dict:
    summary = {state: 0 for state in VERIFY_STATES}
    for item in checks:
        summary[item["state"]] += 1
    status = "failed" if summary["no"] else (
        "incomplete" if summary["unknown"] else "passed"
    )
    return {
        "case": str(path),
        "status": status,
        "summary": summary,
        "checks": checks,
    }


def dry_run_case(path: Path, root: Path = ROOT) -> dict:
    """Describe the selected case and its input hashes without executing it."""
    try:
        case = parse_case(path)
    except CaseError as exc:
        return {
            "case": str(path),
            "error": str(exc),
            "executed": False,
            "inputs": [],
        }
    inputs: list[dict] = []
    for entry in case.get("inputs") or []:
        if not isinstance(entry, str) or not entry.strip():
            inputs.append({"path": str(entry), "sha256": None, "missing": True})
            continue
        resolved = resolve_input(entry, path.parent, root)
        if resolved is None:
            inputs.append({"path": entry, "sha256": None, "missing": True})
            continue
        inputs.append(
            {
                "path": entry,
                "resolved": str(resolved),
                "sha256": path_sha256(resolved),
                "missing": False,
            }
        )
    return {
        "case": str(path),
        "id": case.get("id"),
        "sha256": case["revision"],
        "intent": case.get("intent"),
        "criteria": case.get("criteria") or [],
        "targets": case.get("targets") or [],
        "tools": case.get("tools") or [],
        "inputs": inputs,
        "executed": False,
    }


def read_revisions(log: Path | None = None) -> list[dict]:
    path = REVISION_LOG if log is None else Path(log)
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def revision_warnings(
    case_id: str, revision: str, log: Path | None = None
) -> list[str]:
    warnings: list[str] = []
    other = sorted(
        {
            str(item.get("revision"))
            for item in read_revisions(log)
            if item.get("id") == case_id and item.get("revision") != revision
        }
    )
    if other:
        warnings.append(
            f"{case_id}: aynı ölçüm kimliği altında farklı revision var "
            f"({', '.join(other)}); karşılaştırma revision={revision} ile daraltılmalı"
        )
    return warnings


def record_revision(
    case_id: str,
    revision: str,
    *,
    log: Path | None = None,
    case: Path | None = None,
    at: str | None = None,
) -> tuple[dict, list[str]]:
    """Append one run revision; older revisions stay in the same log."""
    path = REVISION_LOG if log is None else Path(log)
    warnings = revision_warnings(case_id, revision, path)
    record = {
        "demir_kit_version": "2",
        "id": case_id,
        "revision": revision,
        "case": str(case) if case is not None else None,
        "at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record, warnings


def run_case(
    path: Path, log: Path | None = None, at: str | None = None
) -> tuple[dict | None, list[str]]:
    """Freeze the case revision for a run; comparison narrowing stays explicit."""
    errors = check_case_file(path)
    if errors:
        return None, errors
    try:
        case = parse_case(path)
    except CaseError as exc:
        return None, [f"{path}: {exc}"]
    return record_revision(
        str(case["id"]), str(case["revision"]), log=log, case=path, at=at
    )


def agent_variants() -> list[dict]:
    records: list[dict] = []
    for path in sorted(AGENTS.rglob("agent.yaml")):
        role = str(path.parent.relative_to(AGENTS))
        agent = load_yaml(path)
        for cap_id, spec in (agent.get("variants") or {}).items():
            if not isinstance(spec, dict):
                continue
            records.append(
                {
                    "role": role,
                    "capability": cap_id,
                    "eval": spec.get("eval"),
                    "doc": spec.get("doc"),
                    "min_level": spec.get("min_level"),
                    "dir": path.parent,
                }
            )
    return records


def check_all() -> list[str]:
    errors: list[str] = []
    for record in agent_variants():
        eval_rel = str(record.get("eval") or "")
        errors.extend(
            check_eval_file(record["dir"] / eval_rel)
            if eval_rel
            else [f"{record['role']}.{record['capability']}: eval yok"]
        )
    errors.extend(check_findings())
    return errors


def scenario_ids(path: Path) -> list[str]:
    return [row["id"] for row in parse_eval(path)]


def validate_results(payload: dict, expected: list[str], allow_skip: bool = False) -> list[str]:
    errors: list[str] = []
    results = payload.get("results")
    if not isinstance(results, list):
        return ["results liste değil"]
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            errors.append("result öğesi mapping değil")
            continue
        rid = str(item.get("id") or "")
        verdict = item.get("result")
        if rid not in expected:
            errors.append(f"bilinmeyen senaryo ID: {rid}")
        if rid in seen:
            errors.append(f"tekrarlı sonuç ID: {rid}")
        seen.add(rid)
        if verdict not in RESULT_VALUES:
            errors.append(f"{rid}: result pass/fail/skip olmalı")
        elif verdict == "fail":
            errors.append(f"{rid}: fail")
        elif verdict == "skip" and not allow_skip:
            errors.append(f"{rid}: skip")
    for rid in expected:
        if rid not in seen:
            errors.append(f"eksik sonuç: {rid}")
    return errors


def _emit_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _verify_command(paths: list[Path], as_json: bool) -> int:
    results = [verify_case(path) for path in paths]
    if as_json:
        _emit_json({"mode": "verify", "executed": False, "cases": results})
    else:
        for item in results:
            print(f"{item['case']}: {item['status']}")
            for check in item["checks"]:
                print(f"  [{check['state']}] {check['id']}: {check['detail']}")
            summary = item["summary"]
            print(
                f"  {summary['yes']} yes, {summary['no']} no, "
                f"{summary['unknown']} unknown"
            )
    return 1 if any(item["status"] == "failed" for item in results) else 0


def _dry_run_command(paths: list[Path], as_json: bool) -> int:
    results = [dry_run_case(path) for path in paths]
    failed = any("error" in item for item in results)
    if as_json:
        _emit_json(
            {
                "mode": "dry-run",
                "executed": False,
                "status": "failed" if failed else "passed",
                "cases": results,
            }
        )
    else:
        for item in results:
            if "error" in item:
                print(f"{item['case']}: {item['error']}")
                continue
            print(f"{item['case']}: {item.get('id')} {item['sha256']}")
            for entry in item["inputs"]:
                digest = entry.get("sha256") or "yok"
                print(f"  input {entry['path']} {digest}")
        print("dry-run: hiçbir case çalıştırılmadı")
    return 1 if failed else 0


def _run_command(paths: list[Path], log: Path | None, as_json: bool) -> int:
    records: list[dict] = []
    warnings: list[str] = []
    failed = False
    for path in paths:
        record, messages = run_case(path, log=log)
        warnings.extend(messages)
        if record is None:
            failed = True
        else:
            records.append(record)
    if as_json:
        _emit_json(
            {
                "mode": "run",
                "executed": False,
                "status": "failed" if failed else "passed",
                "records": records,
                "warnings": warnings,
            }
        )
    else:
        for record in records:
            print(f"{record['case']}: {record['id']} {record['revision']}")
        for message in warnings:
            print(f"[uyarı] {message}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="capability eval runner")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--role")
    parser.add_argument("--eval")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--allow-skip", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-o", "--output", choices=("text", "json"))
    parser.add_argument("--revision-log", type=Path)
    parser.add_argument("cases", nargs="*", metavar="CASE")
    args = parser.parse_args(argv)

    modes = [args.verify, args.dry_run, args.run]
    if sum(bool(mode) for mode in modes) > 1:
        parser.error("--verify, --dry-run ve --run aynı anda kullanılamaz")
    as_json = args.output == "json" or args.json
    paths = [Path(item) for item in args.cases]

    if args.verify:
        if not paths:
            parser.error("--verify için en az bir case yolu gerekli")
        return _verify_command(paths, as_json)

    if args.dry_run:
        if not paths:
            parser.error("--dry-run için en az bir case yolu gerekli")
        return _dry_run_command(paths, as_json)

    if args.run:
        if not paths:
            parser.error("--run için en az bir case yolu gerekli")
        return _run_command(paths, args.revision_log, as_json)

    if args.check:
        if paths:
            errors = [
                message
                for path in paths
                for message in check_eval_file(path)
            ]
        else:
            errors = check_all()
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    if args.list:
        for record in agent_variants():
            path = record["dir"] / str(record.get("eval") or "")
            count = len(parse_eval(path)) if path.is_file() else 0
            print(
                f"{record['role'].ljust(20)} {record['capability'].ljust(24)} "
                f"{str(record.get('eval')).ljust(18)} {count}"
            )
        return 0

    if args.template:
        if not args.role or not args.eval:
            sys.exit("eval: --template için --role ve --eval gerekli")
        record = next(
            (
                item
                for item in agent_variants()
                if item["role"] == args.role and item["eval"] == args.eval
            ),
            None,
        )
        if not record:
            sys.exit(f"eval: {args.role} / {args.eval} bulunamadı")
        ids = scenario_ids(record["dir"] / args.eval)
        print(
            json.dumps(
                {
                    "role": args.role,
                    "eval": args.eval,
                    "results": [
                        {"id": rid, "result": "pass", "note": ""} for rid in ids
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.results:
        try:
            payload = json.loads(args.results.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.exit(f"eval: {exc}")
        role = payload.get("role")
        eval_name = payload.get("eval")
        record = next(
            (
                item
                for item in agent_variants()
                if item["role"] == role and item["eval"] == eval_name
            ),
            None,
        )
        if not record:
            sys.exit(f"eval: {role} / {eval_name} bulunamadı")
        errors = validate_results(
            payload,
            scenario_ids(record["dir"] / eval_name),
            allow_skip=args.allow_skip,
        )
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
