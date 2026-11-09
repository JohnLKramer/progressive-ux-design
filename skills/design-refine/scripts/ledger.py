"""Findings ledger for the design-refine loop.

The ledger is one JSON file: `version`, `max_iterations`, `bar`, `findings` (id -> finding),
`history` (open count after each ingest) and `total_attempts`. `ingest` validates a whole
critique before it touches the file; invalid input raises `LedgerError` and leaves the file
as it was. Nothing is silently fixed up.

Finding statuses: open, retry, attempted, fixed, unresolved, needs_you, dropped.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent.parent / "style-switcher" / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from problems import Problem, format_problems  # noqa: E402

SEVERITIES = ("P0", "P1", "P2", "P3")
LAYERS = ("STRUCTURAL", "STYLE-ONLY", "AMBIGUOUS")
KINDS = ("execution", "intent", "preference")
FINDING_FIELDS = (
    "same_as",
    "title",
    "layer",
    "severity",
    "kind",
    "before",
    "after",
    "why",
    "fixer_instruction",
)
MAX_FINDINGS = 8
VERSION = 1

ACTIVE_STATUSES = ("open", "retry", "attempted")
NEW = "new"


class LedgerError(Exception):
    def __init__(self, problems: List[Problem]) -> None:
        if not problems:
            raise ValueError("LedgerError requires at least one problem")
        super().__init__(format_problems(problems))
        self.problems = problems


def _fail(code: str, where: str, message: str) -> LedgerError:
    return LedgerError([Problem(code, where, message)])


def _write(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(ledger, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def init_ledger(path: Path, max_iterations: int = 5, bar: str = "P2") -> dict:
    path = Path(path)
    problems: List[Problem] = []
    if bar not in SEVERITIES:
        problems.append(Problem("bad-bar", "bar", "%r is not one of %s" % (bar, ", ".join(SEVERITIES))))
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
        problems.append(Problem("bad-max-iterations", "max_iterations", "%r is not an integer >= 1" % (max_iterations,)))
    if path.exists():
        problems.append(Problem("ledger-exists", str(path), "ledger already exists; refusing to overwrite"))
    if problems:
        raise LedgerError(problems)
    ledger = {
        "version": VERSION,
        "max_iterations": max_iterations,
        "bar": bar,
        "findings": {},
        "history": [],
        "total_attempts": 0,
    }
    _write(path, ledger)
    return ledger


def load_ledger(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise _fail("ledger-missing", str(path), "ledger file does not exist")
    try:
        ledger = json.loads(path.read_text())
    except ValueError as exc:
        raise _fail("ledger-invalid", str(path), "not valid JSON: %s" % exc)
    if not isinstance(ledger, dict) or ledger.get("version") != VERSION:
        got = ledger.get("version") if isinstance(ledger, dict) else ledger
        raise _fail("ledger-version", str(path), "expected version %d, found %r" % (VERSION, got))
    return ledger


def at_or_above_bar(severity: str, bar: str) -> bool:
    return SEVERITIES.index(severity) <= SEVERITIES.index(bar)


def open_count(ledger: dict) -> int:
    return sum(
        1
        for f in ledger["findings"].values()
        if f["status"] in ACTIVE_STATUSES and at_or_above_bar(f["severity"], ledger["bar"])
    )


def _validate_critique(critique: List[dict], known_ids: Dict[str, dict]) -> List[Problem]:
    if not isinstance(critique, list):
        return [Problem("critique-not-list", "critique", "critique must be a list of findings")]
    problems: List[Problem] = []
    if len(critique) > MAX_FINDINGS:
        problems.append(
            Problem("too-many-findings", "critique", "%d findings, at most %d allowed" % (len(critique), MAX_FINDINGS))
        )
    seen: Dict[str, int] = {}
    for i, item in enumerate(critique):
        where = "finding[%d]" % i
        if not isinstance(item, dict):
            problems.append(Problem("finding-not-object", where, "finding must be an object"))
            continue
        for key in sorted(set(item) - set(FINDING_FIELDS)):
            problems.append(Problem("unknown-field", where, "unknown field %r" % key))
        for key in FINDING_FIELDS:
            if key not in item:
                problems.append(Problem("missing-field", where, "missing field %r" % key))
            elif not isinstance(item[key], str) or not item[key].strip():
                problems.append(Problem("bad-field", where, "field %r must be a non-empty string" % key))
        for key, allowed in (("severity", SEVERITIES), ("layer", LAYERS), ("kind", KINDS)):
            value = item.get(key)
            if isinstance(value, str) and value.strip() and value not in allowed:
                problems.append(Problem("bad-" + key, where, "%r is not one of %s" % (value, ", ".join(allowed))))
        same_as = item.get("same_as")
        if isinstance(same_as, str) and same_as.strip() and same_as != NEW:
            if same_as not in known_ids:
                problems.append(Problem("unknown-same-as", where, "same_as %r is not a ledger id" % same_as))
            elif same_as in seen:
                problems.append(
                    Problem("duplicate-same-as", where, "same_as %r already used by finding[%d]" % (same_as, seen[same_as]))
                )
            else:
                seen[same_as] = i
    return problems


def _target_status(item: dict) -> str:
    """Status a finding gets from its own classification, ignoring history."""
    if item["kind"] == "preference":
        return "dropped"
    if item["kind"] == "intent" or item["layer"] == "AMBIGUOUS":
        return "needs_you"
    return "open"


def _stored(item: dict) -> dict:
    return {k: item[k] for k in FINDING_FIELDS if k != "same_as"}


def ingest(path: Path, critique: List[dict]) -> dict:
    path = Path(path)
    ledger = load_ledger(path)
    findings = ledger["findings"]
    problems = _validate_critique(critique, findings)
    if problems:
        raise LedgerError(problems)

    result: Dict[str, List[str]] = {
        "new": [], "matched": [], "fixed": [], "unresolved": [], "needs_you": [], "dropped": [],
    }
    next_number = len(findings) + 1
    mentioned = set()

    for item in critique:
        target = _target_status(item)
        if item["same_as"] == NEW:
            fid = "F%d" % next_number
            next_number += 1
            entry = {"id": fid, **_stored(item), "status": target, "attempts": 0, "approaches": []}
            findings[fid] = entry
            result["new" if target == "open" else target].append(fid)
        else:
            fid = item["same_as"]
            entry = findings[fid]
            previous = entry["status"]
            entry.update(_stored(item))
            mentioned.add(fid)
            if target != "open":
                entry["status"] = target
                result[target].append(fid)
                continue
            result["matched"].append(fid)
            if previous == "attempted":
                if entry["attempts"] >= 2:
                    entry["status"] = "unresolved"
                    result["unresolved"].append(fid)
                else:
                    entry["status"] = "retry"
            elif previous in ("fixed", "dropped", "needs_you"):
                entry["status"] = "open"
            # open, retry, unresolved keep their status

    for fid, entry in findings.items():
        if fid in mentioned or fid in result["new"] or fid in result["needs_you"] or fid in result["dropped"]:
            continue
        if entry["status"] == "attempted":
            entry["status"] = "fixed"
            result["fixed"].append(fid)
        elif entry["status"] in ("open", "retry"):
            entry["status"] = "dropped"
            result["dropped"].append(fid)

    ledger["history"].append(open_count(ledger))
    _write(path, ledger)
    return result
