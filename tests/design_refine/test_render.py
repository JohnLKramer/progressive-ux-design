import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from render import build_styled_copy, render_page
from screenshot import playwright_available, screenshot

RENDER = Path(__file__).resolve().parents[2] / "skills" / "design-refine" / "scripts" / "render.py"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Loaded by file path: tests/style_switcher/fixtures is also a package named `fixtures`.
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "make_workspace.py"
_spec = importlib.util.spec_from_file_location("design_refine_make_workspace", str(_FIXTURE))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
make_workspace = _mod.make_workspace

needs_browser = pytest.mark.skipif(not playwright_available(), reason="Playwright is not importable")


def link_href(html, link_id):
    tag = re.search(r'<link\b[^>]*\bid="%s"[^>]*>' % link_id, html).group(0)
    return re.search(r'\bhref="([^"]*)"', tag).group(1)


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path / "ws")


def test_build_styled_copy_sets_both_hrefs_and_copies_css(ws, tmp_path):
    out = build_styled_copy(ws, "demo", "a", tmp_path / "copy")
    assert out == tmp_path / "copy" / "index.html"
    html = out.read_text(encoding="utf-8")
    assert link_href(html, "sp-style") == "style.css"
    assert link_href(html, "sp-layout") == "layout.css"
    assert (tmp_path / "copy" / "style.css").read_text() == (ws / "styles" / "a" / "style.css").read_text()
    assert (tmp_path / "copy" / "layout.css").read_text() == (ws / "styles" / "a" / "layout.css").read_text()


def test_no_layout_leaves_layout_href_unset(ws, tmp_path):
    out = build_styled_copy(ws, "demo", "a", tmp_path / "copy", layout=False)
    html = out.read_text(encoding="utf-8")
    assert link_href(html, "sp-style") == "style.css"
    assert link_href(html, "sp-layout") == ""
    assert not (tmp_path / "copy" / "layout.css").exists()


def test_style_without_layout_css_renders_style_only(ws, tmp_path):
    (ws / "styles" / "a" / "layout.css").unlink()
    out = build_styled_copy(ws, "demo", "a", tmp_path / "copy")
    assert link_href(out.read_text(encoding="utf-8"), "sp-layout") == ""
    assert not (tmp_path / "copy" / "layout.css").exists()


def test_workspace_is_not_modified(ws, tmp_path):
    before = (ws / "pages" / "demo" / "index.html").read_text()
    build_styled_copy(ws, "demo", "a", tmp_path / "copy")
    assert (ws / "pages" / "demo" / "index.html").read_text() == before


def test_missing_style_raises(ws, tmp_path):
    with pytest.raises(FileNotFoundError):
        build_styled_copy(ws, "demo", "nope", tmp_path / "copy")


def test_missing_page_raises(ws, tmp_path):
    with pytest.raises(FileNotFoundError):
        build_styled_copy(ws, "nope", "a", tmp_path / "copy")


def test_page_without_style_link_raises(ws, tmp_path):
    page = ws / "pages" / "demo" / "index.html"
    page.write_text(page.read_text().replace('<link id="sp-style" rel="stylesheet" href="">', ""))
    with pytest.raises(ValueError):
        build_styled_copy(ws, "demo", "a", tmp_path / "copy")


def run_cli(*args, **env):
    full_env = dict(os.environ)
    full_env.update(env)
    return subprocess.run(
        [sys.executable, str(RENDER)] + [str(a) for a in args],
        capture_output=True, text=True, env=full_env, timeout=120,
    )


def test_cli_exits_3_without_playwright(ws, tmp_path):
    proc = run_cli(
        "--workspace", ws, "--slug", "demo", "--style", "a", "--out", tmp_path / "o.png",
        DESIGN_REFINE_FORCE_NO_BROWSER="1",
    )
    assert proc.returncode == 3
    assert proc.stdout == ""
    assert len(proc.stderr.strip().splitlines()) == 1
    assert not (tmp_path / "o.png").exists()


@needs_browser
def test_render_page_writes_png(ws, tmp_path):
    out = render_page(ws, "demo", "a", tmp_path / "o.png")
    assert out == tmp_path / "o.png"
    data = out.read_bytes()
    assert data.startswith(PNG_SIGNATURE)
    assert len(data) > 1000


@needs_browser
def test_style_actually_applies_in_untrusted_render(ws, tmp_path):
    (ws / "styles" / "a" / "style.css").write_text("body{background:#ff0000;font-size:40px}\n")
    styled = render_page(ws, "demo", "a", tmp_path / "styled.png")
    unstyled = tmp_path / "unstyled.png"
    assert screenshot((ws / "pages" / "demo" / "index.html").resolve().as_uri(), unstyled,
                      untrusted=True, full_page=True)
    assert styled.read_bytes() != unstyled.read_bytes()
    other = render_page(ws, "demo", "b", tmp_path / "b.png")
    assert other.read_bytes() != styled.read_bytes()


@needs_browser
def test_cli_renders_png(ws, tmp_path):
    proc = run_cli("--workspace", ws, "--slug", "demo", "--style", "a", "--out", tmp_path / "o.png", "--no-layout")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "o.png").read_bytes().startswith(PNG_SIGNATURE)


def test_screenshot_failure_raises(ws, tmp_path, monkeypatch):
    import render

    monkeypatch.setattr(render, "screenshot", lambda *a, **k: False)
    with pytest.raises(RuntimeError):
        render_page(ws, "demo", "a", tmp_path / "o.png")
