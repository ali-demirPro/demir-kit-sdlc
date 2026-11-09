#!/usr/bin/env python3
"""Run one agent session in a sandbox and normalize its evidence.

The runner is intentionally small: a session is a temporary directory outside
the repo, a sandbox copy of the source tree, a command list, and five evidence
files (``spec.json``, ``result.json``, ``session/inputs.ndjson``,
``session/events.ndjson``, ``session/diff.patch``).  Everything runs with
python3 and git only; no JavaScript runtime or container engine is involved.

Usage:
  python3 delivery/scripts/eval_run.py --spec spec.json
  python3 delivery/scripts/eval_run.py --spec spec.json --out /tmp/session-1
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

KIT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EPOCH = "1970-01-01T00:00:00+00:00"
SANDBOX_MODES = {"none", "clone", "copy"}
EVIDENCE_FILES = (
    "spec.json",
    "result.json",
    "session/inputs.ndjson",
    "session/events.ndjson",
    "session/diff.patch",
)

STATES = ("preparing", "running", "waiting", "blocked", "terminal")
TRANSITIONS = {
    "preparing": {"running", "blocked", "terminal"},
    "running": {"waiting", "blocked", "terminal"},
    "waiting": {"running", "blocked", "terminal"},
    "blocked": {"running", "terminal"},
    "terminal": set(),
}


class SessionError(RuntimeError):
    """Raised when a session cannot be created or driven safely."""


class StateError(SessionError):
    """Raised for an invalid session state transition."""


# ---------------------------------------------------------------------------
# state machine


class SessionStateMachine:
    """Track preparing/running/waiting/blocked/terminal with a history."""

    def __init__(self, session_dir: Path, state: str = "preparing") -> None:
        if state not in STATES:
            raise StateError(f"bilinmeyen durum: {state}")
        self.session_dir = Path(session_dir)
        self.state = state
        self.history: list[dict] = [
            {
                "from": None,
                "to": state,
                "reason": "",
                "at": _now(),
            }
        ]

    def transition(self, target: str, reason: str = "") -> str:
        if target not in STATES:
            raise StateError(f"bilinmeyen durum: {target}")
        if target not in TRANSITIONS[self.state]:
            raise StateError(f"geçersiz geçiş: {self.state} -> {target}")
        previous = self.state
        self.state = target
        self.history.append(
            {"from": previous, "to": target, "reason": reason, "at": _now()}
        )
        self.save()
        return target

    def snapshot(self) -> dict:
        return {"state": self.state, "history": list(self.history)}

    def save(self) -> Path:
        path = self.session_dir / "state.json"
        _write_json(path, self.snapshot())
        return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# small helpers


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _ndjson_line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_ndjson(path: Path, records: Iterable[dict]) -> Path:
    """Write canonical NDJSON: sorted keys, compact separators, one line each."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_ndjson_line(record) for record in records]
    payload = "".join(line + "\n" for line in lines)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_ndjson(path: Path) -> list[dict]:
    records: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return records
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _seq_value(event: dict) -> int | None:
    for key in ("seq", "id"):
        value = event.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _base_time(raw: str | None) -> datetime:
    text = raw or DEFAULT_EPOCH
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.fromisoformat(DEFAULT_EPOCH)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------------------
# normalization


def normalize_events(
    raw_events: Iterable[dict], observed_at_base: str | None = None
) -> list[dict]:
    """Normalize raw events to ``{seq, turn, observedAt, payload}``.

    ``seq`` comes from the source event identity when it exists (``seq`` or a
    numeric ``id``); otherwise a monotonic counter fills it.  The counter never
    reuses a value, so filtering the result keeps the original gaps.  Nothing
    here is derived from the list index, and the output is a pure function of
    the input, which keeps ``events.ndjson`` reproducible.
    """
    base = _base_time(observed_at_base)
    next_seq = 0
    last_turn = 0
    records: list[dict] = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            raise SessionError("olay kaydı mapping değil")
        source = _seq_value(raw)
        if source is None:
            seq = next_seq
            next_seq += 1
        else:
            seq = source
            next_seq = max(next_seq, seq + 1)

        turn = raw.get("turn")
        if not isinstance(turn, int) or isinstance(turn, bool):
            turn = last_turn
        last_turn = turn

        observed = raw.get("observedAt")
        if not isinstance(observed, str) or not observed:
            observed = (base + timedelta(milliseconds=seq)).isoformat()

        if isinstance(raw.get("payload"), dict):
            payload = dict(raw["payload"])
        else:
            payload = {
                key: value
                for key, value in raw.items()
                if key not in {"seq", "id", "turn", "observedAt", "payload"}
            }

        records.append(
            {
                "seq": seq,
                "turn": turn,
                "observedAt": observed,
                "payload": payload,
            }
        )
    return records


def filter_events(
    events: Iterable[dict], predicate: Callable[[dict], bool]
) -> list[dict]:
    """Filter normalized events without renumbering; gaps stay visible."""
    return [event for event in events if predicate(event)]


def normalize_inputs(raw_inputs: Iterable[object]) -> list[dict]:
    """Normalize declared session inputs without deriving seq from the index."""
    next_seq = 0
    last_turn = 0
    records: list[dict] = []
    for raw in raw_inputs:
        if isinstance(raw, str):
            item: dict = {"text": raw}
        elif isinstance(raw, dict):
            item = dict(raw)
        else:
            raise SessionError("girdi kaydı string veya mapping olmalı")
        source = _seq_value(item)
        if source is None:
            seq = next_seq
            next_seq += 1
        else:
            seq = source
            next_seq = max(next_seq, seq + 1)
        turn = item.get("turn")
        if not isinstance(turn, int) or isinstance(turn, bool):
            turn = last_turn
        last_turn = turn
        records.append(
            {
                "seq": seq,
                "turn": turn,
                "kind": str(item.get("kind") or "prompt"),
                "text": str(item.get("text") or item.get("input") or ""),
            }
        )
    return records


# ---------------------------------------------------------------------------
# sandbox and process capture


def prepare_sandbox(
    source: Path | None, sandbox: Path, mode: str = "clone"
) -> Path:
    """Create the sandbox outside the repo.

    ``clone`` uses ``git clone --shared``; ``copy`` copies a configured tree.
    ``git worktree add`` is deliberately not used (invariant I17).
    """
    if mode not in SANDBOX_MODES:
        raise SessionError(f"bilinmeyen sandbox modu: {mode}")
    sandbox = Path(sandbox)
    if sandbox.exists():
        shutil.rmtree(sandbox)
    if mode == "none":
        sandbox.mkdir(parents=True)
        return sandbox
    if source is None:
        raise SessionError("sandbox için kaynak dizin gerekli")
    source = Path(source)
    if not source.is_dir():
        raise SessionError(f"kaynak dizin yok: {source}")
    if mode == "clone":
        result = subprocess.run(
            ["git", "clone", "--quiet", "--shared", str(source), str(sandbox)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SessionError(
                "sandbox klonu oluşturulamadı: " + (result.stderr or "").strip()
            )
        return sandbox

    shutil.copytree(
        source,
        sandbox,
        ignore=shutil.ignore_patterns(".git", "__pycache__"),
    )
    _git_baseline(sandbox)
    return sandbox


def _git_baseline(sandbox: Path) -> None:
    """Turn a copied tree into a git baseline when git is available."""
    commands = [
        ["git", "init", "--quiet"],
        ["git", "add", "-A"],
        [
            "git",
            "-c",
            "user.email=eval-run@demir-kit.invalid",
            "-c",
            "user.name=eval-run",
            "commit",
            "--quiet",
            "-m",
            "sandbox baseline",
        ],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command, cwd=str(sandbox), capture_output=True, text=True
            )
        except (FileNotFoundError, OSError):
            return
        if result.returncode != 0:
            return


def collect_diff(sandbox: Path, session_dir: Path) -> Path:
    """Write ``session/diff.patch``; an empty sandbox yields an empty patch."""
    target = Path(session_dir) / "session" / "diff.patch"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = ""
    if (Path(sandbox) / ".git").exists():
        try:
            subprocess.run(
                ["git", "add", "-A", "-N"],
                cwd=str(sandbox),
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                ["git", "diff", "--binary", "--no-color"],
                cwd=str(sandbox),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                text = result.stdout
        except (FileNotFoundError, OSError):
            text = ""
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
    return target


def capture_process(
    command: list[str], cwd: Path, timeout: float | int | None
) -> dict:
    """Run a command list without a shell and turn its output into raw events."""
    raw: list[dict] = [
        {"payload": {"type": "process.start", "command": list(command)}}
    ]
    timed_out = False
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode: int | None = result.returncode
        stdout = result.stdout or ""
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = _text(exc.stdout)
        stderr = _text(exc.stderr)
    except (FileNotFoundError, OSError) as exc:
        raw.append(
            {"payload": {"type": "process.error", "error": type(exc).__name__}}
        )
        raw.append({"payload": {"type": "process.exit", "returncode": None}})
        return {
            "events": raw,
            "returncode": None,
            "timed_out": False,
            "unexpected_death": True,
            "reason": "süreç başlatılamadı",
        }

    for stream, text in (("stdout", stdout), ("stderr", stderr)):
        for number, line in enumerate(text.splitlines(), 1):
            raw.append(
                {
                    "payload": {
                        "type": stream,
                        "line": number,
                        "text": line,
                    }
                }
            )
    raw.append({"payload": {"type": "process.exit", "returncode": returncode}})
    unexpected = timed_out or (returncode is not None and returncode < 0)
    if timed_out:
        reason = "zaman aşımı"
    elif unexpected:
        reason = f"beklenmedik ölüm (signal {-returncode})"
    else:
        reason = ""
    return {
        "events": raw,
        "returncode": returncode,
        "timed_out": timed_out,
        "unexpected_death": unexpected,
        "reason": reason,
    }


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


# ---------------------------------------------------------------------------
# evidence references


def _artifact_root(session_dir: Path, attempt: int) -> Path:
    return Path(session_dir) / "attempts" / str(attempt)


def validate_evidence(
    reference: dict,
    events: Iterable[dict],
    session_dir: Path,
    attempts: int = 1,
) -> list[str]:
    """Validate one trace or artifact reference; an empty list means valid."""
    errors: list[str] = []
    if not isinstance(reference, dict):
        return ["kanıt referansı mapping değil"]
    kind = reference.get("kind")
    if kind not in {"trace", "artifact"}:
        return [f"bilinmeyen kanıt türü: {kind!r}"]
    if kind == "trace":
        seq = reference.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            errors.append("trace.seq negatif olmayan tam sayı olmalı")
        else:
            seen = {
                event.get("seq")
                for event in events
                if isinstance(event, dict)
            }
            if seq not in seen:
                errors.append(f"trace.seq olay kaydında yok: {seq}")
        return errors

    artifact = reference.get("artifact")
    attempt = reference.get("attempt", 1)
    line = reference.get("line")
    if not isinstance(artifact, str) or not artifact:
        return ["artifact yolu boş"]
    if artifact.startswith("/") or "\\" in artifact or ".." in artifact.split("/"):
        return [f"artifact yolu oturum dışına çıkıyor: {artifact}"]
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        errors.append("artifact.attempt 1 veya daha büyük olmalı")
        attempt = 0
    elif attempt > attempts:
        errors.append(f"artifact.attempt deneme sınırı dışında: {attempt}>{attempts}")
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        errors.append("artifact.line 1 tabanlı tam sayı olmalı")
        line = 0
    if errors:
        return errors

    root = _artifact_root(session_dir, attempt)
    if not _inside(root / artifact, root):
        return [f"artifact yolu oturum dışına çıkıyor: {artifact}"]
    path = root / artifact
    if not path.is_file():
        return [f"artifact dosyası yok: attempt {attempt} / {artifact}"]
    try:
        total = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError as exc:
        return [f"artifact okunamadı: {exc}"]
    if line > total:
        errors.append(f"artifact.line dosya dışında: {line}>{total}")
    return errors


def validate_references(
    references: Iterable[dict],
    events: Iterable[dict],
    session_dir: Path,
    attempts: int = 1,
) -> list[str]:
    """Validate every reference, prefixing errors with its position."""
    errors: list[str] = []
    events = list(events)
    for index, reference in enumerate(references):
        for message in validate_evidence(reference, events, session_dir, attempts):
            errors.append(f"evidence[{index}]: {message}")
    return errors


# ---------------------------------------------------------------------------
# session directory, spec and result


def _normalize_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise SessionError("spec mapping değil")
    case = spec.get("case")
    if not isinstance(case, str) or not case.strip():
        raise SessionError("spec.case boş olamaz")
    command = spec.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(part, str) and part for part in command)
    ):
        raise SessionError("spec.command boş olmayan string listesi olmalı")
    mode = spec.get("sandbox", "none")
    if mode not in SANDBOX_MODES:
        raise SessionError(f"spec.sandbox geçersiz: {mode}")
    attempts = spec.get("attempts", 1)
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        raise SessionError("spec.attempts pozitif tam sayı olmalı")
    timeout = spec.get("timeout", 300)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise SessionError("spec.timeout pozitif sayı olmalı")
    inputs = spec.get("inputs", [])
    if not isinstance(inputs, list):
        raise SessionError("spec.inputs liste olmalı")
    normalized = dict(spec)
    normalized.update(
        {
            "demir_kit_version": "2",
            "case": case.strip(),
            "command": list(command),
            "sandbox": mode,
            "attempts": attempts,
            "timeout": timeout,
            "inputs": list(inputs),
        }
    )
    return normalized


def default_session_dir() -> Path:
    """Create a temporary session directory outside the repository."""
    path = Path(tempfile.mkdtemp(prefix="demir-eval-", dir=tempfile.gettempdir()))
    if _inside(path, KIT_ROOT):
        shutil.rmtree(path, ignore_errors=True)
        raise SessionError(
            "geçici dizin repo içinde; TMPDIR repo dışında olmalı"
        )
    return path.resolve()


def resolve_session_dir(out_dir: Path | None) -> Path:
    if out_dir is None:
        return default_session_dir()
    path = Path(out_dir).expanduser().resolve()
    if _inside(path, KIT_ROOT):
        raise SessionError("oturum dizini repo içinde olamaz")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _archive_previous(session_dir: Path, attempt: int) -> None:
    """Copy the current canonical files into attempts/<attempt>/ before reuse."""
    target = _artifact_root(session_dir, attempt)
    if target.exists():
        return
    for relative in EVIDENCE_FILES:
        source = session_dir / relative
        if source.is_file():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _mirror_attempt(session_dir: Path, attempt: int) -> None:
    target = _artifact_root(session_dir, attempt)
    for relative in EVIDENCE_FILES:
        source = session_dir / relative
        if source.is_file():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _recovery(session_dir: Path, reason: str, attempt: int, maximum: int) -> dict:
    script = Path(__file__).resolve()
    return {
        "reason": reason,
        "evidence_dir": str(session_dir),
        "evidence_intact": True,
        "attempt": attempt,
        "attempts_left": max(0, maximum - attempt),
        "resume_command": (
            f"python3 {script} --spec {session_dir / 'spec.json'}"
            f" --out {session_dir}"
        ),
    }


def run_session(
    spec: dict,
    out_dir: Path | None = None,
    base_dir: Path | None = None,
) -> dict:
    """Prepare, run and record one session; blocked sessions keep evidence."""
    normalized = _normalize_spec(spec)
    if base_dir is not None:
        out_dir = Path(base_dir) if out_dir is None else Path(out_dir)
    session_dir = resolve_session_dir(out_dir)
    session = session_dir / "session"
    session.mkdir(parents=True, exist_ok=True)

    previous = _read_json(session_dir / "result.json")
    attempt = int(previous.get("attempt") or 0) + 1
    maximum = int(normalized["attempts"])
    if attempt > maximum:
        raise SessionError(
            f"deneme sınırı aşıldı: {attempt}>{maximum}"
        )
    if attempt > 1:
        _archive_previous(session_dir, attempt - 1)

    machine = SessionStateMachine(session_dir)
    machine.save()
    _write_json(session_dir / "spec.json", normalized)

    inputs_path = session / "inputs.ndjson"
    events_path = session / "events.ndjson"
    diff_path = session / "diff.patch"
    write_ndjson(inputs_path, normalize_inputs(normalized["inputs"]))
    write_ndjson(events_path, [])
    diff_path.write_text("", encoding="utf-8")

    sandbox = session_dir / "sandbox"
    capture: dict = {
        "events": [],
        "returncode": None,
        "timed_out": False,
        "unexpected_death": False,
        "reason": "",
    }
    blocked_reason = ""
    try:
        prepare_sandbox(
            Path(normalized["source"]).expanduser()
            if normalized.get("source")
            else None,
            sandbox,
            normalized["sandbox"],
        )
        machine.transition("running", "sandbox hazır")
        capture = capture_process(
            normalized["command"], sandbox, normalized["timeout"]
        )
        if capture["unexpected_death"]:
            blocked_reason = capture["reason"] or "beklenmedik süreç sonu"
            machine.transition("blocked", blocked_reason)
        else:
            machine.transition("terminal", "süreç bitti")
    except SessionError as exc:
        blocked_reason = str(exc)
        if machine.state not in {"blocked", "terminal"}:
            machine.transition("blocked", blocked_reason)
    except Exception as exc:  # noqa: BLE001 - evidence must survive any failure
        blocked_reason = f"{type(exc).__name__}: {exc}"
        if machine.state not in {"blocked", "terminal"}:
            machine.transition("blocked", blocked_reason)

    events = normalize_events(
        capture["events"], normalized.get("created_at")
    )
    write_ndjson(events_path, events)
    try:
        collect_diff(sandbox, session_dir)
    except OSError:
        diff_path.write_text("", encoding="utf-8")

    status = "blocked" if blocked_reason else (
        "pass" if capture["returncode"] == 0 else "fail"
    )
    result = {
        "demir_kit_version": "2",
        "case": normalized["case"],
        "attempt": attempt,
        "attempts": attempt,
        "state": machine.state,
        "status": status,
        "exit_code": capture["returncode"],
        "timed_out": bool(capture["timed_out"]),
        "unexpected_death": bool(capture["unexpected_death"]),
        "event_count": len(events),
        "evidence": list(EVIDENCE_FILES),
        "recovery": (
            _recovery(session_dir, blocked_reason, attempt, maximum)
            if blocked_reason
            else None
        ),
    }
    _write_json(session_dir / "result.json", result)
    _mirror_attempt(session_dir, attempt)
    return result


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="run one agent session")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        spec = _read_json(args.spec)
    except OSError as exc:
        print(f"eval_run: spec okunamadı: {exc}", file=sys.stderr)
        return 3
    if not spec:
        print(f"eval_run: spec boş veya geçersiz: {args.spec}", file=sys.stderr)
        return 3
    try:
        result = run_session(spec, out_dir=args.out)
    except SessionError as exc:
        print(f"eval_run: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"] == "blocked":
        return 2
    if result["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
