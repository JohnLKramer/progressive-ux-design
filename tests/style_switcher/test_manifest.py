from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fixtures.make_workspace import make_workspace
from manifest import build_manifest, slugify, style_display_name, validate_manifest, write_manifest


def codes(problems):
    return sorted(p.code for p in problems)


def test_slugify_basic_collision_and_fallback():
    assert slugify("ClassPass | Profile", set()) == "classpass-profile"
    taken = {"classpass-profile"}
    assert slugify("ClassPass | Profile", taken) == "classpass-profile-2"
    assert taken == {"classpass-profile"}
    assert slugify("ClassPass | Profile", {"classpass-profile", "classpass-profile-2"}) == "classpass-profile-3"
    assert slugify("!!!", set()) == "page"


def test_style_display_name(tmp_path):
    ws = make_workspace(tmp_path, styles=[("a", "  Big Box Gym\n", False), ("b", None, False), ("c", "  \n", False)])
    assert style_display_name(ws / "styles" / "a") == "Big Box Gym"
    assert style_display_name(ws / "styles" / "b") == "b"
    assert style_display_name(ws / "styles" / "c") == "c"


def test_build_manifest_contents_and_ordering(tmp_path):
    ws = make_workspace(
        tmp_path,
        pages=[("zeta", "Zeta &amp; Co"), ("alpha", "  Alpha\n Page ")],
        styles=[("b", None, True), ("a", "Name A", False)],
    )
    (ws / "pages" / "zeta" / "index.html").write_text("<html><body></body></html>", encoding="utf-8")
    (ws / "pages" / ".DS_Store").write_text("", encoding="utf-8")
    (ws / "styles" / ".DS_Store").write_text("", encoding="utf-8")
    assert build_manifest(ws) == {
        "pages": [{"slug": "alpha", "title": "Alpha Page"}, {"slug": "zeta", "title": "zeta"}],
        "styles": [
            {"id": "a", "name": "Name A", "hasLayout": False},
            {"id": "b", "name": "b", "hasLayout": True},
        ],
    }


def test_page_title_entities_decoded(tmp_path):
    ws = make_workspace(tmp_path, pages=[("p", "Tom &amp; Jerry")])
    assert build_manifest(ws)["pages"] == [{"slug": "p", "title": "Tom & Jerry"}]


def test_write_manifest_is_deterministic(tmp_path):
    ws = make_workspace(tmp_path, pages=[("b", "B"), ("a", "A")], styles=[("s", "Ünï", True)])
    path = write_manifest(ws)
    assert path == ws / "manifest.json"
    first = path.read_bytes()
    write_manifest(ws)
    assert path.read_bytes() == first
    assert first.endswith(b"\n")
    assert "Ünï".encode("utf-8") in first


def test_validate_clean_workspace(tmp_path):
    ws = make_workspace(tmp_path, styles=[("a", None, True), ("b", "B", False)])
    write_manifest(ws)
    assert validate_manifest(ws) == []


def test_validate_missing_workspace_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_manifest(tmp_path / "nope")


def test_empty_pages_and_styles(tmp_path):
    ws = make_workspace(tmp_path, pages=[], styles=[])
    write_manifest(ws)
    assert codes(validate_manifest(ws)) == ["empty", "empty"]
    ws2 = make_workspace(tmp_path / "w2", pages=[("p", "P")], styles=[])
    write_manifest(ws2)
    assert codes(validate_manifest(ws2)) == ["empty"]


def test_missing_manifest_is_malformed(tmp_path):
    ws = make_workspace(tmp_path)
    assert codes(validate_manifest(ws)) == ["malformed"]


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        '{"pages": []}',
        '{"pages": {}, "styles": []}',
        '{"pages": [{"slug": "home"}], "styles": []}',
        '{"pages": [{"slug": 1, "title": "x"}], "styles": []}',
        '{"pages": [], "styles": [{"id": "a", "name": "A", "hasLayout": "yes"}]}',
        '{"pages": [], "styles": [{"id": "a", "name": "A"}]}',
        '{"pages": ["x"], "styles": []}',
    ],
)
def test_malformed_manifests(tmp_path, content):
    ws = make_workspace(tmp_path)
    (ws / "manifest.json").write_text(content, encoding="utf-8")
    assert "malformed" in codes(validate_manifest(ws))


def test_duplicates(tmp_path):
    ws = make_workspace(tmp_path)
    m = {
        "pages": [{"slug": "home", "title": "H"}, {"slug": "home", "title": "H"}],
        "styles": [
            {"id": "plain", "name": "P", "hasLayout": False},
            {"id": "plain", "name": "P", "hasLayout": False},
        ],
    }
    (ws / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    assert codes(validate_manifest(ws)) == ["duplicate-style-id", "malformed"]


def test_missing_files(tmp_path):
    ws = make_workspace(tmp_path, styles=[("a", None, False), ("b", None, False), ("c", None, False)])
    write_manifest(ws)
    (ws / "pages" / "home" / "index.html").unlink()
    (ws / "styles" / "a" / "style.css").unlink()
    (ws / "styles" / "b" / "tokens.json").unlink()
    m = json.loads((ws / "manifest.json").read_text(encoding="utf-8"))
    m["styles"][2]["hasLayout"] = True
    (ws / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    problems = validate_manifest(ws)
    assert codes(problems) == ["missing-file"] * 4
    assert any("home" in p.where for p in problems)


def test_directories_without_files_are_listed_then_reported(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "pages" / "bare").mkdir()
    (ws / "styles" / "bare").mkdir()
    write_manifest(ws)
    assert [p["slug"] for p in build_manifest(ws)["pages"]] == ["bare", "home"]
    assert codes(validate_manifest(ws)) == ["missing-file"] * 3


MANIFEST_SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "style-switcher" / "scripts" / "manifest.py"


def run_manifest(*args):
    return subprocess.run(
        [sys.executable, "-I", str(MANIFEST_SCRIPT), *args], capture_output=True, text=True, timeout=30
    )


def test_slug_command_prints_slug():
    result = run_manifest("slug", "ClassPass | Profile")
    assert (result.returncode, result.stdout) == (0, "classpass-profile\n")


def test_slug_command_avoids_taken():
    result = run_manifest("slug", "ClassPass | Profile", "--taken", "classpass-profile")
    assert result.stdout == "classpass-profile-2\n"


def test_slug_command_falls_back_to_page():
    assert run_manifest("slug", "!!!").stdout == "page\n"


@pytest.mark.parametrize("args", [[], ["slug"], ["bogus", "x"]])
def test_slug_command_usage_errors(args):
    result = run_manifest(*args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
