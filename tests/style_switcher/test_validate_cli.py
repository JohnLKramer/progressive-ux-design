from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

VALIDATE = Path(__file__).resolve().parents[2] / "skills" / "style-switcher" / "scripts" / "validate.py"
TOKENS = {k: {} for k in ("palette", "fonts", "scale", "spacing", "radii", "shadows")}


def run(*args):
    return subprocess.run(
        [sys.executable, "-I", str(VALIDATE)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def make_style(tmp_path, layout=None):
    d = tmp_path / "style"
    d.mkdir()
    (d / "style.css").write_text("a{color:red}", encoding="utf-8")
    (d / "tokens.json").write_text(json.dumps(TOKENS), encoding="utf-8")
    if layout is not None:
        (d / "layout.css").write_text(layout, encoding="utf-8")
    return d


def test_clean_style_exits_0(tmp_path):
    result = run("style", make_style(tmp_path))
    assert (result.returncode, result.stdout) == (0, "")


def test_problems_exit_1(tmp_path):
    result = run("style", make_style(tmp_path, layout=".n{display:none}"))
    assert result.returncode == 1
    assert "layout-hides" in result.stdout


def test_usage_errors_exit_2(tmp_path):
    for args in ([], ["bogus", "x"], ["style"], ["style", "a", "b"]):
        result = run(*args)
        assert result.returncode == 2, args
        assert "usage" in result.stderr


def test_missing_source_el_ids_file_exits_2(tmp_path):
    page = tmp_path / "p.html"
    page.write_text('<link id="sp-style"><link id="sp-layout">', encoding="utf-8")
    result = run("page", page, "--source-el-ids", tmp_path / "nope.txt")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1
    assert "nope.txt" in result.stderr


def _page(tmp_path, body):
    page = tmp_path / "page.html"
    page.write_text('<link id="sp-style"><link id="sp-layout">' + body, encoding="utf-8")
    return page


def test_source_html_lost_id_exits_1(tmp_path):
    src = tmp_path / "src.html"
    src.write_text('<p data-el="a"></p><p data-el="b"></p>', encoding="utf-8")
    result = run("page", _page(tmp_path, '<p data-el="a"></p>'), "--source-html", src)
    assert result.returncode == 1
    assert "lost-data-el" in result.stdout
    assert "b" in result.stdout


def test_source_html_kept_ids_exits_0(tmp_path):
    src = tmp_path / "src.html"
    src.write_text('<p data-el="a"></p>', encoding="utf-8")
    page = tmp_path / "page.html"
    page.write_text(
        '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<link id="sp-style" rel="stylesheet">\n'
        '<link id="sp-layout" rel="stylesheet">\n</head>\n<body><p data-el="a"></p></body>\n</html>\n',
        encoding="utf-8",
    )
    result = run("page", page, "--source-html", src)
    assert (result.returncode, result.stdout) == (0, "")


def test_both_source_options_exit_2(tmp_path):
    src = tmp_path / "src.html"
    src.write_text("", encoding="utf-8")
    ids = tmp_path / "ids.txt"
    ids.write_text("a\n", encoding="utf-8")
    result = run("page", _page(tmp_path, ""), "--source-html", src, "--source-el-ids", ids)
    assert result.returncode == 2
    assert len(result.stderr.strip().splitlines()) == 1
    assert "Traceback" not in result.stderr


def test_missing_source_html_exits_2(tmp_path):
    result = run("page", _page(tmp_path, ""), "--source-html", tmp_path / "nope.html")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1
    assert "nope.html" in result.stderr


def test_manifest_clean_exits_0(tmp_path):
    from fixtures.make_workspace import make_workspace
    from manifest import write_manifest

    ws = make_workspace(tmp_path / "ws")
    write_manifest(ws)
    result = run("manifest", ws)
    assert (result.returncode, result.stdout) == (0, "")


def test_manifest_problem_exits_1(tmp_path):
    from fixtures.make_workspace import make_workspace
    from manifest import write_manifest

    ws = make_workspace(tmp_path / "ws")
    write_manifest(ws)
    (ws / "styles" / "plain" / "style.css").unlink()
    result = run("manifest", ws)
    assert result.returncode == 1
    assert "missing-file" in result.stdout


def test_manifest_usage_errors_exit_2(tmp_path):
    for args in (["manifest"], ["manifest", "a", "b"]):
        result = run(*args)
        assert result.returncode == 2, args
        assert "usage" in result.stderr


def test_manifest_missing_workspace_exits_2(tmp_path):
    result = run("manifest", tmp_path / "nope")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
