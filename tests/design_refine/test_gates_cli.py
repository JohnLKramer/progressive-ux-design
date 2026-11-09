import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GATES = Path(__file__).resolve().parents[2] / "skills" / "design-refine" / "scripts" / "gates.py"

# Loaded by file path: tests/style_switcher/fixtures is also a package named `fixtures`.
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "make_workspace.py"
_spec = importlib.util.spec_from_file_location("design_refine_make_workspace", str(_FIXTURE))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
make_workspace = _mod.make_workspace


def run(*args):
    return subprocess.run(
        [sys.executable, "-I", str(GATES)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path / "ws")


def snap_args(ws, *extra):
    return ["snapshot", "--workspace", ws, "--slug", "demo", "--style", "a",
            "--dest", ws / ".design-refine" / "s1"] + list(extra)


def test_cli_snapshot_check_restore_cycle(ws):
    snap = run(*snap_args(ws, "--cross-style", "b"))
    assert snap.returncode == 0, snap.stderr
    data = json.loads(snap.stdout)
    assert (data["slug"], data["style_id"], data["cross_style"]) == ("demo", "a", "b")
    dest = ws / ".design-refine" / "s1"

    clean = run("check", "--snapshot", dest, "--kind", "structural")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout == ""

    page = ws / "pages" / "demo" / "index.html"
    original = page.read_text(encoding="utf-8")
    page.write_text(original.replace('data-el="El2"', 'data-el="El9"'), encoding="utf-8")
    bad = run("check", "--snapshot", dest, "--kind", "structural")
    assert bad.returncode == 1
    assert "marker-lost" in bad.stdout

    restored = run("restore", "--snapshot", dest)
    assert restored.returncode == 0, restored.stderr
    assert page.read_text(encoding="utf-8") == original
    assert run("check", "--snapshot", dest, "--kind", "structural").returncode == 0


def test_check_exits_1_with_problem_codes(ws):
    assert run(*snap_args(ws)).returncode == 0
    dest = ws / ".design-refine" / "s1"
    (ws / "styles" / "b" / "style.css").write_text("body{color:red}\n", encoding="utf-8")
    result = run("check", "--snapshot", dest, "--kind", "style")
    assert result.returncode == 1
    assert "file-out-of-scope: styles/b/style.css" in result.stdout
    assert "Traceback" not in result.stderr


def test_default_cross_style_is_first_other_style_with_layout(ws):
    for sid in ("0", "c"):
        shutil.copytree(str(ws / "styles" / "a"), str(ws / "styles" / sid))
    (ws / "styles" / "0" / "layout.css").unlink()
    result = run(*snap_args(ws))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["cross_style"] == "b"


def test_no_other_style_prints_null_cross_style(ws):
    shutil.rmtree(str(ws / "styles" / "b"))
    result = run(*snap_args(ws))
    assert result.returncode == 0, result.stderr
    assert '"cross_style": null' in result.stdout


def test_missing_page_exits_1_without_traceback(ws):
    result = run("snapshot", "--workspace", ws, "--slug", "nope", "--style", "a",
                 "--dest", ws / ".design-refine" / "s1")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "nope" in result.stdout


def test_malformed_snapshot_exits_1_without_traceback(tmp_path):
    (tmp_path / "snapshot.json").write_text("{not json", encoding="utf-8")
    for cmd in (("check", "--kind", "style"), ("restore",)):
        result = run(cmd[0], "--snapshot", tmp_path, *cmd[1:])
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "not valid JSON" in result.stdout


def test_usage_errors_exit_2(ws):
    assert run().returncode == 2
    assert run("check", "--snapshot", ws, "--kind", "bogus").returncode == 2


def test_cli_snapshot_with_root_symlinked_outside_is_gate_error(ws, tmp_path):
    outside = tmp_path / "outside-page"
    shutil.move(str(ws / "pages" / "demo"), str(outside))
    (ws / "pages" / "demo").symlink_to(outside, target_is_directory=True)
    result = run(*snap_args(ws))
    assert result.returncode == 1
    assert result.stdout.startswith("gate-error: snapshot: SnapshotError:")
    assert "outside the workspace" in result.stdout
    assert not (ws / ".design-refine" / "s1").exists()
