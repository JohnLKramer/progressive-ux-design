"""Scripted design-refine loop: the real CLIs, driven in the order SKILL.md gives, with canned
critique JSON files standing in for the critic and the fixer. No script is mocked."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "design-refine" / "scripts"

# Loaded by file path: tests/style_switcher/fixtures is also a package named `fixtures`.
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "make_workspace.py"
_spec = importlib.util.spec_from_file_location("design_refine_make_workspace", str(_FIXTURE))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
make_workspace = _mod.make_workspace


def _run(script, *args):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPTS / script)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def ledger(*args):
    return _run("ledger.py", *args)


def gates(*args):
    return _run("gates.py", *args)


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def finding(same_as="new", title="Cancel outweighs Book", severity="P1", layer="STYLE-ONLY"):
    return {
        "same_as": same_as,
        "title": title,
        "layer": layer,
        "severity": severity,
        "kind": "execution",
        "before": "Cancel is a solid red button the same size as Book.",
        "after": "Book is the only filled button in the row.",
        "why": "Nielsen #5 Error prevention.",
        "fixer_instruction": "Make Book the only filled button and restyle Cancel as an outline.",
    }


class Loop:
    """One style's loop, as the skill runs it."""

    def __init__(self, tmp_path, max_iterations=5):
        self.ws = make_workspace(tmp_path / "ws")
        self.log = self.ws / ".design-refine" / "demo--a"
        self.log.mkdir(parents=True)
        self.ledger = self.log / "ledger.json"
        self.iteration = 0
        ok(ledger("init", self.ledger, "--max-iterations", max_iterations))

    @property
    def page(self):
        return self.ws / "pages" / "demo" / "index.html"

    @property
    def css(self):
        return self.ws / "styles" / "a" / "style.css"

    @property
    def snap(self):
        return self.log / ("iter-%d" % self.iteration) / "snapshot"

    def review(self, critique):
        """Steps 2-4: view, save the critique, ingest, status. Returns the status."""
        self.iteration += 1
        iter_dir = self.log / ("iter-%d" % self.iteration)
        iter_dir.mkdir()
        view_text = ok(ledger("view", self.ledger))
        (iter_dir / "ledger-view.json").write_text(view_text, encoding="utf-8")
        for entry in json.loads(view_text):
            assert "approaches" not in entry
        crit = iter_dir / "critique.json"
        crit.write_text(json.dumps(critique), encoding="utf-8")
        ok(ledger("ingest", self.ledger, crit))
        return json.loads(ok(ledger("status", self.ledger)))

    def next_finding(self):
        return json.loads(ok(ledger("next", self.ledger)))

    def snapshot(self):
        ok(gates("snapshot", "--workspace", self.ws, "--slug", "demo", "--style", "a",
                 "--dest", self.snap))

    def check(self, kind="style"):
        return gates("check", "--snapshot", self.snap, "--kind", kind)

    def attempt(self, fid, result, approach="canned fix"):
        return json.loads(ok(ledger("attempt", self.ledger, fid, "--approach", approach, "--result", result)))

    def kept_style_fix(self, fid):
        """Steps 6-8 and 11 for a fix that passes: snapshot, edit the CSS, check, keep."""
        self.snapshot()
        self.css.write_text(self.css.read_text(encoding="utf-8") + ".btn-cancel{background:none}\n",
                            encoding="utf-8")
        assert ok(self.check()) == ""
        return self.attempt(fid, "kept")

    def report(self):
        return ok(ledger("report", self.ledger))


@pytest.fixture
def loop(tmp_path):
    return Loop(tmp_path)


def test_happy_path_ends_bar_clear(loop):
    status = loop.review([finding()])
    assert status == {"stop": False, "reason": None, "next": "F1"}
    chosen = loop.next_finding()
    assert chosen["id"] == "F1"
    assert chosen["status"] == "open"

    entry = loop.kept_style_fix("F1")
    assert (entry["status"], entry["attempts"]) == ("attempted", 1)

    status = loop.review([])
    assert status == {"stop": True, "reason": "bar-clear", "next": None}
    ledger_data = json.loads(loop.ledger.read_text(encoding="utf-8"))
    assert ledger_data["findings"]["F1"]["status"] == "fixed"
    assert "- F1 (P1): Cancel outweighs Book" in loop.report().split("## Unresolved")[0]


def test_failed_gate_restores_and_counts_attempt(loop):
    loop.review([finding(layer="STRUCTURAL")])
    chosen = loop.next_finding()
    assert chosen["layer"] == "STRUCTURAL"
    loop.snapshot()
    original = loop.page.read_bytes()

    loop.page.write_bytes(original.replace(b'data-el="El2"', b'data-el="El9"'))
    bad = loop.check("structural")
    assert bad.returncode == 1
    assert "marker-lost" in bad.stdout

    ok(gates("restore", "--snapshot", loop.snap))
    assert loop.page.read_bytes() == original
    assert loop.check("structural").returncode == 0

    entry = loop.attempt("F1", "gate-failed", "removed a data-el marker")
    assert (entry["status"], entry["attempts"]) == ("retry", 1)
    assert entry["approaches"] == ["removed a data-el marker"]

    # The finding is selectable again, and the critic's view of it never shows the approach.
    assert loop.next_finding()["id"] == "F1"
    loop.review([finding(same_as="F1", layer="STRUCTURAL")])
    view = json.loads((loop.log / "iter-2" / "ledger-view.json").read_text(encoding="utf-8"))
    assert view[0]["status"] == "retry"
    assert view[0]["attempts"] == 1
    assert "approaches" not in view[0]


def test_same_finding_twice_ends_unresolved_and_loop_stops(loop):
    loop.review([finding()])
    loop.kept_style_fix("F1")

    status = loop.review([finding(same_as="F1")])
    assert status["stop"] is False
    assert status["next"] == "F1"
    assert loop.next_finding()["status"] == "retry"
    loop.kept_style_fix("F1")

    status = loop.review([finding(same_as="F1")])
    assert status["stop"] is True
    assert status["next"] is None
    assert json.loads(loop.ledger.read_text(encoding="utf-8"))["findings"]["F1"]["status"] == "unresolved"

    unresolved = loop.report().split("## Unresolved")[1].split("## Needs you")[0]
    assert "- F1 (P1): Cancel outweighs Book" in unresolved
    assert "Evidence: Cancel is a solid red button the same size as Book." in unresolved
    assert "Attempt 1: canned fix" in unresolved
    assert "Attempt 2: canned fix" in unresolved
    assert "## Fixed\n\nNone." in loop.report()


def test_cap_stops_before_a_further_attempt(tmp_path):
    # A small cap keeps the test short; the cap check is the same comparison whatever the value
    # (total_attempts >= max_iterations), so this exercises the default-5 path too.
    cap = 2
    loop = Loop(tmp_path, max_iterations=cap)
    attempts = 0
    status = loop.review([finding(title="Finding 1")])
    while not status["stop"]:
        fid = status["next"]
        loop.kept_style_fix(fid)
        attempts += 1
        assert attempts <= cap, "the loop ran past the cap"
        # Each review reports a different new finding, so the bar never clears.
        status = loop.review([finding(title="Finding %d" % (attempts + 1))])

    assert status["reason"] == "cap"
    assert attempts == cap
    assert status["next"] is not None  # work remained: the cap, not an empty bar, stopped it
    assert json.loads(loop.ledger.read_text(encoding="utf-8"))["total_attempts"] == cap
    report = loop.report()
    still_open = report[report.index("## Still open"):report.index("## Needs you")]
    assert "%s (" % status["next"] in still_open
    assert "Finding %d" % (cap + 1) in still_open
