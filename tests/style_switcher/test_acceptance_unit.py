from __future__ import annotations

import pytest

from acceptance import check_assets, run_acceptance
from fixtures.make_workspace import make_workspace
from screenshot import playwright_available


def _ws(tmp_path, page_body="", style_css=None):
    ws = make_workspace(
        tmp_path / "ws",
        pages=[("home", "Home")],
        styles=[("plain", None, False), ("bold", "Bold", True)],
    )
    index = ws / "pages" / "home" / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("<body></body>", "<body>%s</body>" % page_body), encoding="utf-8")
    if style_css is not None:
        (ws / "styles" / "bold" / "style.css").write_text(style_css, encoding="utf-8")
    for style in ("plain", "bold"):
        (ws / "styles" / style / "notes.md").write_text("notes", encoding="utf-8")
    return ws


def _codes(problems):
    return [p.code for p in problems]


def test_missing_page_asset_is_reported(tmp_path):
    ws = _ws(tmp_path, '<img src="assets/x.png">')
    problems = check_assets(ws)
    assert _codes(problems) == ["missing-file"]
    assert "assets/x.png" in problems[0].message


def test_existing_css_url_is_clean(tmp_path):
    ws = _ws(tmp_path, style_css="@font-face{src:url(assets/f.woff2)}")
    (ws / "styles" / "bold" / "assets").mkdir()
    (ws / "styles" / "bold" / "assets" / "f.woff2").write_bytes(b"x")
    assert check_assets(ws) == []


def test_missing_css_url_is_reported(tmp_path):
    ws = _ws(tmp_path, style_css="a{background:url('assets/nope.png')}")
    problems = check_assets(ws)
    assert _codes(problems) == ["missing-file"]
    assert "assets/nope.png" in problems[0].message


def test_data_uris_and_fragments_are_ignored(tmp_path):
    ws = _ws(
        tmp_path,
        page_body='<img src="data:image/png;base64,AAAA"><a href="#top">t</a>',
        style_css="a{background:url(data:image/png;base64,AAAA)} b{fill:url(#grad)}",
    )
    assert check_assets(ws) == []


def test_path_escaping_the_workspace_is_reported(tmp_path):
    (tmp_path / "outside.png").write_bytes(b"x")
    ws = _ws(tmp_path, '<img src="../../../outside.png">')
    assert _codes(check_assets(ws)) == ["missing-file"]


def test_remote_links_are_ignored(tmp_path):
    ws = _ws(tmp_path, '<a href="https://example.com/x">x</a>')
    assert check_assets(ws) == []


needs_browser = pytest.mark.skipif(not playwright_available(), reason="Playwright is not importable")


@needs_browser
def test_acceptance_detects_failures(tmp_path, capsys):
    ws = _ws(tmp_path, '<img src="assets/planted-missing.png">')
    code = run_acceptance(ws, tmp_path / "out")
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code != 0
    assert "planted-missing.png" in text
    assert "missing-file" in text
    assert "Failed to load resource" in text


@needs_browser
def test_acceptance_passes_on_clean_workspace(tmp_path):
    ws = _ws(tmp_path)
    out = tmp_path / "out"
    assert run_acceptance(ws, out) == 0
    contact = (out / "contact.html").read_text(encoding="utf-8")
    assert "<script" not in contact
    assert len(list((out / "shots").glob("*.png"))) == 4
    assert (out / "notes" / "bold.md").is_file()


@needs_browser
def test_acceptance_fails_without_notes(tmp_path, capsys):
    ws = _ws(tmp_path)
    (ws / "styles" / "plain" / "notes.md").unlink()
    assert run_acceptance(ws, tmp_path / "out") != 0
    captured = capsys.readouterr()
    assert "notes.md" in captured.out + captured.err


@needs_browser
def test_contact_sheet_shots_cover_the_whole_page(tmp_path):
    ws = _ws(tmp_path, page_body="<p>line</p>" * 400)
    out = tmp_path / "out"
    assert run_acceptance(ws, out) == 0
    for shot in (out / "shots").glob("*.png"):
        data = shot.read_bytes()
        height = int.from_bytes(data[20:24], "big")
        assert height > 900, shot.name
