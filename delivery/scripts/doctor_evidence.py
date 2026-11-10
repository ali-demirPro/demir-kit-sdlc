"""Evidence test reporting for doctor (not_run honesty).

Kept out of doctor.py so the module split budget stays intact.
"""

from __future__ import annotations

import evidence


def report_not_run(cp_id: str, tests, note) -> dict:
    """Print each not-run row with its reason, then the run/not-run counts."""
    for test in tests if isinstance(tests, list) else []:
        if not isinstance(test, dict) or test.get("result") != "not_run":
            continue
        note(
            f"{cp_id} not_run: {test.get('case')} — "
            f"{test.get('note') or 'gerekçe yok'}"
        )
    summary = evidence.summarize_tests(tests)
    if summary["not_run"]:
        note(
            f"{cp_id}: {summary['ran']} koştu, "
            f"{summary['not_run']} koşmadı"
        )
    return summary


def report_evidence_tests(records: dict, note) -> None:
    """Report not-run rows for every record, before any status gate."""
    for cp_id, record in records.items():
        if isinstance(record, dict):
            report_not_run(cp_id, record.get("tests") or [], note)
