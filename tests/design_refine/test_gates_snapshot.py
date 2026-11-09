import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import gates

# Loaded by file path: tests/style_switcher/fixtures is also a package named `fixtures`
# with a make_workspace module, so `from fixtures.make_workspace import ...` could pick
# up the wrong one when both test directories run in one session.
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "make_workspace.py"
_spec = importlib.util.spec_from_file_location("design_refine_make_workspace", str(_FIXTURE))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
make_workspace = _mod.make_workspace


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path / "ws")


def _snap(ws, **kwargs):
    dest = ws / ".design-refine" / "snap-1"
    gates.snapshot(ws, "demo", "a", dest, **kwargs)
    return dest


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- fixture -------------------------------------------------------------


def test_fixture_page_and_styles_are_valid(ws):
    from validate_page import validate_page
    from validate_style import validate_style

    assert validate_page(ws / "pages" / "demo" / "index.html") == []
    assert validate_style(ws / "styles" / "a") == []
    assert validate_style(ws / "styles" / "b") == []


# --- snapshot ------------------------------------------------------------


def test_snapshot_copies_roots_and_records_hashes(ws):
    (ws / ".design-refine" / "old").mkdir(parents=True)
    (ws / ".design-refine" / "old" / "junk.txt").write_text("x", encoding="utf-8")
    dest = ws / ".design-refine" / "snap-1"
    data = gates.snapshot(ws, "demo", "a", dest, cross_style="b")

    assert (dest / "roots" / "pages" / "demo" / "index.html").read_bytes() == (
        ws / "pages" / "demo" / "index.html"
    ).read_bytes()
    assert (dest / "roots" / "styles" / "a" / "style.css").is_file()
    assert (dest / "roots" / "styles" / "b" / "tokens.json").is_file()

    on_disk = json.loads((dest / "snapshot.json").read_text(encoding="utf-8"))
    assert on_disk == data
    assert sorted(r["path"] for r in data["roots"]) == sorted(
        str((ws / p).resolve()) for p in ("pages/demo", "styles/a", "styles/b")
    )
    assert data["hashes"]["pages/demo/index.html"] == _sha(ws / "pages" / "demo" / "index.html")
    assert set(data["hashes"]) == {
        "pages/demo/index.html",
        "styles/a/style.css",
        "styles/a/layout.css",
        "styles/a/tokens.json",
        "styles/b/style.css",
        "styles/b/layout.css",
        "styles/b/tokens.json",
    }


def test_snapshot_hashing_excludes_only_design_refine(ws):
    (ws / "notes.txt").write_text("n", encoding="utf-8")
    (ws / "pages" / ".design-refine-not").mkdir()
    (ws / "pages" / ".design-refine-not" / "f.txt").write_text("f", encoding="utf-8")
    data = gates.snapshot(ws, "demo", "a", ws / ".design-refine" / "s")
    assert "notes.txt" in data["hashes"]
    assert "pages/.design-refine-not/f.txt" in data["hashes"]
    assert not any(k.startswith(".design-refine/") for k in data["hashes"])


def test_snapshot_with_doc_outside_workspace(ws, tmp_path):
    doc = tmp_path / "design.md"
    doc.write_text("# doc\n", encoding="utf-8")
    data = gates.snapshot(ws, "demo", "a", ws / ".design-refine" / "s", doc=doc)
    assert data["doc"] == str(doc.resolve())
    doc_roots = [r for r in data["roots"] if r["path"] == str(doc.resolve())]
    assert len(doc_roots) == 1 and doc_roots[0]["kind"] == "file"
    assert (ws / ".design-refine" / "s" / doc_roots[0]["copy"]).read_text(encoding="utf-8") == "# doc\n"


def test_snapshot_refuses_non_empty_dest(ws):
    dest = ws / ".design-refine" / "s"
    dest.mkdir(parents=True)
    (dest / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        gates.snapshot(ws, "demo", "a", dest)
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (dest / "snapshot.json").exists()


def test_snapshot_accepts_existing_empty_dest(ws):
    dest = ws / ".design-refine" / "s"
    dest.mkdir(parents=True)
    gates.snapshot(ws, "demo", "a", dest)
    assert (dest / "snapshot.json").is_file()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slug": "nope", "style_id": "a"},
        {"slug": "demo", "style_id": "nope"},
        {"slug": "demo", "style_id": "a", "cross_style": "nope"},
    ],
)
def test_snapshot_missing_page_or_style_raises(ws, kwargs):
    dest = ws / ".design-refine" / "s"
    with pytest.raises(FileNotFoundError):
        gates.snapshot(ws, dest=dest, **kwargs)
    assert not (dest / "snapshot.json").exists()


def test_snapshot_page_dir_without_index_raises(ws):
    (ws / "pages" / "demo" / "index.html").unlink()
    with pytest.raises(FileNotFoundError):
        gates.snapshot(ws, "demo", "a", ws / ".design-refine" / "s")


def test_snapshot_missing_doc_raises(ws, tmp_path):
    with pytest.raises(FileNotFoundError):
        gates.snapshot(ws, "demo", "a", ws / ".design-refine" / "s", doc=tmp_path / "nope.md")


@pytest.mark.parametrize("bad", ["..", "../ws", "a/b", "", "."])
def test_snapshot_rejects_path_like_names(ws, bad):
    with pytest.raises(ValueError):
        gates.snapshot(ws, bad, "a", ws / ".design-refine" / "s")
    with pytest.raises(ValueError):
        gates.snapshot(ws, "demo", bad, ws / ".design-refine" / "s")


def test_snapshot_rejects_cross_style_equal_to_primary(ws):
    with pytest.raises(ValueError):
        gates.snapshot(ws, "demo", "a", ws / ".design-refine" / "s", cross_style="a")


def test_snapshot_rejects_dest_inside_a_root(ws):
    with pytest.raises(ValueError):
        gates.snapshot(ws, "demo", "a", ws / "pages" / "demo" / "snap")


def test_snapshot_rejects_dest_in_workspace_outside_design_refine(ws):
    # Its copies would be hashed as workspace files on the next check.
    with pytest.raises(ValueError):
        gates.snapshot(ws, "demo", "a", ws / "snap")


def test_snapshot_dest_outside_workspace_is_allowed(ws, tmp_path):
    gates.snapshot(ws, "demo", "a", tmp_path / "elsewhere")
    assert (tmp_path / "elsewhere" / "snapshot.json").is_file()


# --- check ---------------------------------------------------------------

PAGE = Path("pages") / "demo" / "index.html"


def _edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _codes(problems):
    return [p.code for p in problems]


def test_untouched_workspace_passes_both_kinds(ws):
    dest = _snap(ws, cross_style="b")
    assert gates.check(dest, "structural") == []
    assert gates.check(dest, "style") == []


def test_structural_kind_allows_page_edit(ws):
    dest = _snap(ws)
    _edit(ws / PAGE, "<h2>Popular today</h2>", '<div class="wrap"><h2>Popular today</h2></div>')
    (ws / "pages" / "demo" / "extra.css").write_text("x{}", encoding="utf-8")
    assert gates.check(dest, "structural") == []


def test_style_kind_allows_primary_style_edit(ws):
    dest = _snap(ws)
    (ws / "styles" / "a" / "style.css").write_text("body{color:#000}\n", encoding="utf-8")
    assert gates.check(dest, "style") == []


def test_style_kind_rejects_page_edit(ws):
    dest = _snap(ws)
    _edit(ws / PAGE, "Popular today", "Popular now")
    problems = gates.check(dest, "style")
    assert _codes(problems) == ["file-out-of-scope"]
    assert problems[0].where == "pages/demo/index.html"
    assert "cannot be auto-reverted" not in problems[0].message


def test_structural_kind_rejects_style_edit(ws):
    dest = _snap(ws)
    (ws / "styles" / "a" / "style.css").write_text("body{color:#000}\n", encoding="utf-8")
    problems = gates.check(dest, "structural")
    assert _codes(problems) == ["file-out-of-scope"]
    assert problems[0].where == "styles/a/style.css"
    assert "cannot be auto-reverted" not in problems[0].message


def test_style_kind_rejects_cross_style_edit_but_it_is_revertable(ws):
    dest = _snap(ws, cross_style="b")
    (ws / "styles" / "b" / "style.css").write_text("body{color:#000}\n", encoding="utf-8")
    problems = gates.check(dest, "style")
    assert _codes(problems) == ["file-out-of-scope"]
    assert "cannot be auto-reverted" not in problems[0].message


def test_edit_to_other_page_is_out_of_scope_and_unrevertable(ws):
    other = ws / "pages" / "other"
    other.mkdir()
    (other / "index.html").write_text("<p>other</p>", encoding="utf-8")
    dest = _snap(ws)
    (other / "index.html").write_text("<p>changed</p>", encoding="utf-8")
    for kind in ("structural", "style"):
        problems = gates.check(dest, kind)
        assert _codes(problems) == ["file-out-of-scope"]
        assert problems[0].where == "pages/other/index.html"
        assert "cannot be auto-reverted" in problems[0].message


def test_added_and_removed_files_outside_roots_are_out_of_scope(ws):
    (ws / "README.txt").write_text("r", encoding="utf-8")
    dest = _snap(ws)
    (ws / "README.txt").unlink()
    (ws / "new.txt").write_text("n", encoding="utf-8")
    problems = gates.check(dest, "structural")
    assert sorted(p.where for p in problems) == ["README.txt", "new.txt"]
    assert set(_codes(problems)) == {"file-out-of-scope"}
    assert all("cannot be auto-reverted" in p.message for p in problems)
    assert "removed" in [p for p in problems if p.where == "README.txt"][0].message
    assert "added" in [p for p in problems if p.where == "new.txt"][0].message


def test_design_refine_dir_changes_are_ignored(ws):
    dest = _snap(ws)
    (ws / ".design-refine" / "log.txt").write_text("l", encoding="utf-8")
    assert gates.check(dest, "structural") == []


def test_doc_inside_workspace_is_in_scope_for_structural_only(ws):
    doc = ws / "design.md"
    doc.write_text("# doc\n", encoding="utf-8")
    dest = _snap(ws, doc=doc)
    doc.write_text("# doc v2\n", encoding="utf-8")
    assert gates.check(dest, "structural") == []
    problems = gates.check(dest, "style")
    assert _codes(problems) == ["file-out-of-scope"]
    assert problems[0].where == "design.md"
    assert "cannot be auto-reverted" not in problems[0].message


def test_doc_outside_workspace_is_in_scope_for_structural_only(ws, tmp_path):
    doc = tmp_path / "design.md"
    doc.write_text("# doc\n", encoding="utf-8")
    dest = _snap(ws, doc=doc)
    doc.write_text("# doc v2\n", encoding="utf-8")
    assert gates.check(dest, "structural") == []
    problems = gates.check(dest, "style")
    assert _codes(problems) == ["file-out-of-scope"]
    assert problems[0].where == str(doc.resolve())


def test_marker_loss_fails_check(ws):
    dest = _snap(ws)
    _edit(ws / PAGE, ' data-variant="primary"', "")
    _edit(ws / PAGE, ' data-el="El5"', "")
    problems = gates.check(dest, "structural")
    assert _codes(problems) == ["marker-lost", "marker-lost", "lost-data-el"]
    assert any('data-variant="primary"' in p.message for p in problems)


def test_page_validator_problems_are_reported(ws):
    dest = _snap(ws)
    _edit(ws / PAGE, '<section class="hero"', '<section style="color:red" class="hero"')
    assert _codes(gates.check(dest, "structural")) == ["inline-style"]


def test_style_validator_problems_are_reported(ws):
    dest = _snap(ws)
    (ws / "styles" / "a" / "layout.css").write_text("section{display:none}\n", encoding="utf-8")
    assert _codes(gates.check(dest, "style")) == ["layout-hides"]


def test_check_runs_gates_in_order(ws):
    dest = _snap(ws)
    _edit(ws / PAGE, ' data-el="El5"', ' style="x:y"')
    (ws / "styles" / "a" / "tokens.json").write_text("{}", encoding="utf-8")
    assert _codes(gates.check(dest, "structural")) == [
        "file-out-of-scope",
        "marker-lost",
        "inline-style",
        "lost-data-el",
        "bad-tokens",
    ]


def test_deleted_page_is_reported_not_raised(ws):
    dest = _snap(ws)
    (ws / PAGE).unlink()
    assert _codes(gates.check(dest, "structural")) == ["page-missing"]


def test_check_rejects_unknown_kind(ws):
    dest = _snap(ws)
    with pytest.raises(ValueError):
        gates.check(dest, "layout")


def test_check_missing_snapshot_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        gates.check(tmp_path, "structural")


def test_check_malformed_snapshot_raises(ws):
    dest = _snap(ws)
    (dest / "snapshot.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        gates.check(dest, "structural")
