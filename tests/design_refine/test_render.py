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
    assert link_href(html, "sp-style") == "style/style.css"
    assert link_href(html, "sp-layout") == "style/layout.css"
    copy = tmp_path / "copy"
    assert (copy / "style" / "style.css").read_text() == (ws / "styles" / "a" / "style.css").read_text()
    assert (copy / "style" / "layout.css").read_text() == (ws / "styles" / "a" / "layout.css").read_text()


def test_no_layout_leaves_layout_href_unset(ws, tmp_path):
    out = build_styled_copy(ws, "demo", "a", tmp_path / "copy", layout=False)
    html = out.read_text(encoding="utf-8")
    assert link_href(html, "sp-style") == "style/style.css"
    assert link_href(html, "sp-layout") == ""


def test_style_without_layout_css_renders_style_only(ws, tmp_path):
    (ws / "styles" / "a" / "layout.css").unlink()
    out = build_styled_copy(ws, "demo", "a", tmp_path / "copy")
    assert link_href(out.read_text(encoding="utf-8"), "sp-layout") == ""
    assert not (tmp_path / "copy" / "style" / "layout.css").exists()


def test_style_assets_are_copied_beside_the_linked_css_and_do_not_clash_with_page_assets(ws, tmp_path):
    (ws / "styles" / "a" / "assets").mkdir()
    (ws / "styles" / "a" / "assets" / "x.svg").write_text("<svg/>")
    (ws / "pages" / "demo" / "assets").mkdir()
    (ws / "pages" / "demo" / "assets" / "x.svg").write_text("<svg id='page'/>")
    out = build_styled_copy(ws, "demo", "a", tmp_path / "copy")
    css_dir = out.parent / Path(link_href(out.read_text(encoding="utf-8"), "sp-style")).parent
    assert (css_dir / "assets" / "x.svg").read_text() == "<svg/>"
    assert (out.parent / "assets" / "x.svg").read_text() == "<svg id='page'/>"


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


def pixel(png_path, x, y):
    """RGB of one pixel of an 8-bit RGB/RGBA non-interlaced PNG, using only the stdlib."""
    import struct
    import zlib

    data = Path(png_path).read_bytes()
    assert data.startswith(PNG_SIGNATURE)
    pos, idat, header = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    width, height, depth, color_type, _, _, interlace = header
    assert depth == 8 and color_type in (2, 6) and interlace == 0, header
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    raw = zlib.decompress(idat)
    prev = bytearray(stride)
    for row in range(y + 1):
        base = row * (stride + 1)
        ftype, line = raw[base], bytearray(raw[base + 1:base + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ftype == 1:
                line[i] = (line[i] + a) & 255
            elif ftype == 2:
                line[i] = (line[i] + b) & 255
            elif ftype == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        prev = line
    return tuple(prev[x * bpp:x * bpp + 3])


@needs_browser
def test_style_css_actually_applies_in_untrusted_render(ws, tmp_path):
    (ws / "styles" / "a" / "style.css").write_text("html,body{background:#ff0000}\n")
    styled = render_page(ws, "demo", "a", tmp_path / "styled.png", layout=False)
    unstyled = tmp_path / "unstyled.png"
    assert screenshot((ws / "pages" / "demo" / "index.html").resolve().as_uri(), unstyled,
                      untrusted=True, full_page=True)
    assert pixel(styled, 2, 2) == (255, 0, 0)
    assert pixel(unstyled, 2, 2) == (255, 255, 255)


@needs_browser
def test_style_asset_url_resolves_in_render(ws, tmp_path):
    assets = ws / "styles" / "a" / "assets"
    assets.mkdir()
    (assets / "bg.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#00ff00"/></svg>'
    )
    (ws / "styles" / "a" / "style.css").write_text("html,body{background:url(assets/bg.svg)}\n")
    out = render_page(ws, "demo", "a", tmp_path / "o.png", layout=False)
    assert pixel(out, 2, 2) == (0, 255, 0)


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
