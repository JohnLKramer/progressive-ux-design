import json
import subprocess
import sys
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "skills" / "design-refine" / "scripts" / "ledger.py"


def run(*args):
    return subprocess.run(
        [sys.executable, "-I", str(LEDGER)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def finding(**over):
    base = {
        "same_as": "new",
        "title": "Cancel is the loudest button",
        "layer": "STRUCTURAL",
        "severity": "P1",
        "kind": "execution",
        "before": "Cancel is filled and larger than Book",
        "after": "Book is the primary action",
        "why": "Nielsen: aesthetic and minimalist design",
        "fixer_instruction": "Make Cancel a quiet secondary action.",
    }
    base.update(over)
    return base


def write_critique(tmp_path, items):
    p = tmp_path / "critique.json"
    p.write_text(json.dumps(items))
    return p


def test_init_then_ingest_then_next_roundtrip(tmp_path):
    ledger = tmp_path / "ledger.json"
    init = run("init", ledger, "--max-iterations", "3", "--bar", "P1")
    assert init.returncode == 0, init.stderr
    data = json.loads(init.stdout)
    assert (data["max_iterations"], data["bar"]) == (3, "P1")

    ing = run("ingest", ledger, write_critique(tmp_path, [finding()]))
    assert ing.returncode == 0, ing.stderr
    assert json.loads(ing.stdout)["new"] == ["F1"]

    nxt = run("next", ledger)
    assert nxt.returncode == 0, nxt.stderr
    assert json.loads(nxt.stdout)["id"] == "F1"

    att = run("attempt", ledger, "F1", "--approach", "quiet the cancel button", "--result", "kept")
    assert att.returncode == 0, att.stderr
    assert json.loads(att.stdout)["status"] == "attempted"

    rep = run("report", ledger)
    assert rep.returncode == 0, rep.stderr
    assert rep.stdout.startswith("# Design refine report")


def test_next_prints_null_when_nothing_left(tmp_path):
    ledger = tmp_path / "ledger.json"
    assert run("init", ledger).returncode == 0
    result = run("next", ledger)
    assert result.returncode == 0
    assert json.loads(result.stdout) is None


def test_bad_critique_exits_1_and_prints_problem_code(tmp_path):
    ledger = tmp_path / "ledger.json"
    assert run("init", ledger).returncode == 0
    result = run("ingest", ledger, write_critique(tmp_path, [finding(severity="P9")]))
    assert result.returncode == 1
    assert "bad-severity" in result.stdout


def test_unreadable_critique_exits_1_with_problem(tmp_path):
    ledger = tmp_path / "ledger.json"
    assert run("init", ledger).returncode == 0
    bad = tmp_path / "critique.json"
    bad.write_text("{nope")
    result = run("ingest", ledger, bad)
    assert result.returncode == 1
    assert "critique-invalid" in result.stdout
    assert "Traceback" not in result.stderr


def test_missing_ledger_exits_1(tmp_path):
    result = run("status", tmp_path / "nope.json")
    assert result.returncode == 1
    assert "ledger-missing" in result.stdout


def test_unknown_subcommand_exits_2():
    for args in ([], ["bogus", "x"], ["init"], ["attempt", "l", "F1"], ["next", "a", "b"]):
        result = run(*args)
        assert result.returncode == 2, args
        assert "usage" in result.stderr


def test_non_integer_max_iterations_exits_2(tmp_path):
    result = run("init", tmp_path / "l.json", "--max-iterations", "many")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_status_json_has_stop_reason_next(tmp_path):
    ledger = tmp_path / "ledger.json"
    assert run("init", ledger).returncode == 0
    run("ingest", ledger, write_critique(tmp_path, [finding()]))
    result = run("status", ledger)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"stop": False, "reason": None, "next": "F1"}
