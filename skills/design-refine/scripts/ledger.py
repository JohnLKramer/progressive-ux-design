"""Findings ledger for the design-refine loop.

The ledger is one JSON file: `version`, `max_iterations`, `bar`, `findings` (id -> finding),
`history` (open count after each ingest) and `total_attempts`. `ingest` validates a whole
critique before it touches the file; invalid input raises `LedgerError` and leaves the file
as it was. Nothing is silently fixed up.

Finding statuses: open, retry, attempted, fixed, unresolved, needs_you, dropped.
"""
from __future__ import annotations

import argparse
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
    problems = _validate_ledger(ledger)
    if problems:
        raise LedgerError(problems)
    return ledger


STATUSES = ACTIVE_STATUSES + ("fixed", "unresolved", "needs_you", "dropped")
LEDGER_KEYS = ("max_iterations", "bar", "findings", "history", "total_attempts")
STORED_FIELDS = tuple(k for k in FINDING_FIELDS if k != "same_as")


def _is_int(value: object, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validate_ledger(ledger: dict) -> List[Problem]:
    problems: List[Problem] = []
    for key in LEDGER_KEYS:
        if key not in ledger:
            problems.append(Problem("ledger-missing-key", key, "ledger has no %r" % key))
    if problems:
        return problems
    if ledger["bar"] not in SEVERITIES:
        problems.append(Problem("ledger-bad-bar", "bar", "%r is not one of %s" % (ledger["bar"], ", ".join(SEVERITIES))))
    if not _is_int(ledger["max_iterations"], 1):
        problems.append(Problem("ledger-bad-max-iterations", "max_iterations", "%r is not an integer >= 1" % (ledger["max_iterations"],)))
    if not _is_int(ledger["total_attempts"], 0):
        problems.append(Problem("ledger-bad-total-attempts", "total_attempts", "%r is not an integer >= 0" % (ledger["total_attempts"],)))
    history = ledger["history"]
    if not isinstance(history, list) or not all(_is_int(h, 0) for h in history):
        problems.append(Problem("ledger-bad-history", "history", "history must be a list of integers >= 0"))
    findings = ledger["findings"]
    if not isinstance(findings, dict):
        problems.append(Problem("ledger-bad-findings", "findings", "findings must be an object keyed by id"))
        return problems
    for fid, entry in findings.items():
        where = "findings.%s" % fid
        if not isinstance(entry, dict):
            problems.append(Problem("ledger-finding-not-object", where, "finding must be an object"))
            continue
        for key in ("id",) + STORED_FIELDS + ("status", "attempts", "approaches"):
            if key not in entry:
                problems.append(Problem("ledger-finding-missing-field", where, "missing field %r" % key))
        if "id" in entry and (
            entry["id"] != fid or not isinstance(fid, str) or not fid.startswith("F") or not fid[1:].isdigit()
        ):
            problems.append(Problem("ledger-finding-bad-id", where, "id %r does not match key %r or is not F<number>" % (entry["id"], fid)))
        for key in STORED_FIELDS:
            if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
                problems.append(Problem("ledger-finding-bad-field", where, "field %r must be a non-empty string" % key))
        for key, allowed in (("severity", SEVERITIES), ("layer", LAYERS), ("kind", KINDS), ("status", STATUSES)):
            if key in entry and entry[key] not in allowed:
                problems.append(Problem("ledger-finding-bad-" + key, where, "%r is not one of %s" % (entry[key], ", ".join(allowed))))
        if "attempts" in entry and not _is_int(entry["attempts"], 0):
            problems.append(Problem("ledger-finding-bad-attempts", where, "attempts must be an integer >= 0"))
        if "approaches" in entry and (
            not isinstance(entry["approaches"], list) or not all(isinstance(a, str) for a in entry["approaches"])
        ):
            problems.append(Problem("ledger-finding-bad-approaches", where, "approaches must be a list of strings"))
    return problems


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


ATTEMPT_RESULTS = ("kept", "gate-failed", "worse")
SELECTABLE_STATUSES = ("open", "retry")
MAX_ATTEMPTS = 2
NO_PROGRESS_WINDOW = 3


def _id_number(fid: str) -> int:
    return int(fid[1:])


def next_finding(ledger: dict) -> Optional[dict]:
    candidates = [
        f
        for f in ledger["findings"].values()
        if f["status"] in SELECTABLE_STATUSES and at_or_above_bar(f["severity"], ledger["bar"])
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda f: (SEVERITIES.index(f["severity"]), f["layer"] != "STRUCTURAL", _id_number(f["id"])),
    )


def record_attempt(path: Path, finding_id: str, approach: str, result: str) -> dict:
    path = Path(path)
    ledger = load_ledger(path)
    problems: List[Problem] = []
    entry = ledger["findings"].get(finding_id)
    if entry is None:
        problems.append(Problem("unknown-finding", "finding_id", "%r is not a ledger id" % (finding_id,)))
    elif entry["status"] not in SELECTABLE_STATUSES:
        problems.append(
            Problem("not-attemptable", finding_id, "status is %r, expected one of %s" % (entry["status"], ", ".join(SELECTABLE_STATUSES)))
        )
    if result not in ATTEMPT_RESULTS:
        problems.append(Problem("bad-result", "result", "%r is not one of %s" % (result, ", ".join(ATTEMPT_RESULTS))))
    if not isinstance(approach, str) or not approach.strip():
        problems.append(Problem("bad-approach", "approach", "approach must be a non-empty string"))
    if problems:
        raise LedgerError(problems)

    entry["attempts"] += 1
    entry["approaches"].append(approach)
    ledger["total_attempts"] += 1
    if result == "kept":
        entry["status"] = "attempted"
    elif entry["attempts"] >= MAX_ATTEMPTS:
        entry["status"] = "unresolved"
    else:
        entry["status"] = "retry"
    _write(path, ledger)
    return entry


def status(ledger: dict) -> dict:
    upcoming = next_finding(ledger)
    next_id = upcoming["id"] if upcoming else None
    history = ledger["history"]
    recent = history[-NO_PROGRESS_WINDOW:]
    if ledger["total_attempts"] >= ledger["max_iterations"]:
        reason: Optional[str] = "cap"
    elif upcoming is None:
        reason = "bar-clear"
    elif len(recent) == NO_PROGRESS_WINDOW and all(a <= b for a, b in zip(recent, recent[1:])):
        reason = "no-progress"
    else:
        reason = None
    return {"stop": reason is not None, "reason": reason, "next": next_id}


VIEW_FIELDS = ("id",) + STORED_FIELDS + ("status", "attempts")


def view(ledger: dict) -> List[dict]:
    """The findings as the review critic may see them: never the fixers' `approaches`."""
    findings = sorted(ledger["findings"].values(), key=lambda f: _id_number(f["id"]))
    return [{k: f[k] for k in VIEW_FIELDS} for f in findings]


def _section(title: str, lines: List[str]) -> List[str]:
    return ["## " + title, ""] + (lines if lines else ["None."]) + [""]


def report(ledger: dict) -> str:
    findings = sorted(ledger["findings"].values(), key=lambda f: _id_number(f["id"]))
    fixed = [
        "- %s (%s): %s" % (f["id"], f["severity"], f["title"]) for f in findings if f["status"] == "fixed"
    ]
    unresolved: List[str] = []
    for f in (f for f in findings if f["status"] == "unresolved"):
        unresolved.append("- %s (%s): %s" % (f["id"], f["severity"], f["title"]))
        unresolved.append("  - Evidence: %s" % f["before"])
        for number, approach in enumerate(f["approaches"], 1):
            unresolved.append("  - Attempt %d: %s" % (number, approach))
        unresolved.append("  - This may be not a real issue or needs a different kind of fix.")
    still_open: List[str] = []
    for f in findings:
        if f["status"] in ACTIVE_STATUSES and at_or_above_bar(f["severity"], ledger["bar"]):
            still_open.append("- %s (%s, %s): %s" % (f["id"], f["severity"], f["layer"], f["title"]))
            still_open.append("  - Evidence: %s" % f["before"])
            still_open.append("  - Attempts: %d" % f["attempts"])
    needs_you = [
        "- %s (%s): %s - %s" % (f["id"], f["severity"], f["title"], f["why"])
        for f in findings
        if f["status"] == "needs_you"
    ]
    needs_you += [
        "- Declined preference %s (%s): %s - %s" % (f["id"], f["severity"], f["title"], f["why"])
        for f in findings
        if f["status"] == "dropped" and f["kind"] == "preference"
    ]
    below_bar: List[str] = []
    for f in findings:
        if f["status"] in ACTIVE_STATUSES and not at_or_above_bar(f["severity"], ledger["bar"]):
            below_bar.append("- %s (%s, %s): %s" % (f["id"], f["severity"], f["layer"], f["title"]))
            below_bar.append("  - Evidence: %s" % f["before"])
    no_longer_seen: List[str] = []
    for f in findings:
        if f["status"] == "dropped" and f["kind"] != "preference":
            no_longer_seen.append("- %s (%s, %s): %s" % (f["id"], f["severity"], f["layer"], f["title"]))
            no_longer_seen.append("  - Evidence: %s" % f["before"])
            no_longer_seen.append("  - Attempts: %d" % f["attempts"])
    attempts = ["- %s: %d" % (f["id"], f["attempts"]) for f in findings if f["attempts"]]
    lines = ["# Design refine report", ""]
    lines += _section("Fixed", fixed)
    lines += _section("Unresolved", unresolved)
    lines += _section("Still open", still_open)
    lines += _section("Needs you", needs_you)
    lines += _section("Below bar", below_bar)
    lines += _section("No longer seen", no_longer_seen)
    lines += _section("Attempts per finding", attempts)
    return "\n".join(lines)


def _load_critique(path: Path) -> list:
    if not path.is_file():
        raise _fail("critique-missing", str(path), "critique file does not exist")
    try:
        return json.loads(path.read_text())
    except ValueError as exc:
        raise _fail("critique-invalid", str(path), "not valid JSON: %s" % exc)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledger.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("ledger", type=Path)
    p.add_argument("--max-iterations", type=int, default=5)
    p.add_argument("--bar", default="P2")
    p = sub.add_parser("ingest")
    p.add_argument("ledger", type=Path)
    p.add_argument("critique", type=Path)
    for name in ("next", "status", "report", "view"):
        sub.add_parser(name).add_argument("ledger", type=Path)
    p = sub.add_parser("attempt")
    p.add_argument("ledger", type=Path)
    p.add_argument("id")
    p.add_argument("--approach", required=True)
    p.add_argument("--result", required=True)
    return parser


def _dispatch(args: argparse.Namespace) -> str:
    def dump(value: object) -> str:
        return json.dumps(value, indent=2)

    if args.command == "init":
        return dump(init_ledger(args.ledger, args.max_iterations, args.bar))
    if args.command == "ingest":
        return dump(ingest(args.ledger, _load_critique(args.critique)))
    if args.command == "attempt":
        return dump(record_attempt(args.ledger, args.id, args.approach, args.result))
    ledger = load_ledger(args.ledger)
    if args.command == "next":
        return dump(next_finding(ledger))
    if args.command == "status":
        return dump(status(ledger))
    if args.command == "view":
        return dump(view(ledger))
    return report(ledger)


def main(argv: List[str]) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        output = _dispatch(args)
    except LedgerError as exc:
        print(format_problems(exc.problems))
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
