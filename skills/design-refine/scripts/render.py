"""Styled copy and screenshot for design-refine.

A styled copy is a scratch directory holding one page plus one style's CSS, with the page's
`sp-style` / `sp-layout` links pointed at the copied files. It needs nothing outside its own
directory, so it is screenshotted in untrusted mode (no scripts, no remote loads).

Runs as plain `python3`, not `-I`: Playwright lives in user site-packages.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent.parent / "style-switcher" / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from screenshot import playwright_available, screenshot  # noqa: E402

EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NO_PLAYWRIGHT = 3
FORCE_NO_BROWSER_ENV = "DESIGN_REFINE_FORCE_NO_BROWSER"


def _set_link_href(html: str, link_id: str, href: str) -> str:
    pattern = re.compile(r"<link\b[^>]*\bid=[\"']%s[\"'][^>]*>" % re.escape(link_id), re.IGNORECASE)
    match = pattern.search(html)
    if match is None:
        raise ValueError('page has no <link id="%s">' % link_id)
    tag = re.sub(r"\s+href\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", match.group(0), flags=re.IGNORECASE)
    tag = re.sub(r"\s*/?>$", lambda m: ' href="%s"%s' % (href, m.group(0).lstrip()), tag)
    return html[: match.start()] + tag + html[match.end():]


def build_styled_copy(workspace: Path, slug: str, style_id: str, out_dir: Path, layout: bool = True) -> Path:
    page_dir = Path(workspace) / "pages" / slug
    style_dir = Path(workspace) / "styles" / style_id
    if not (page_dir / "index.html").is_file():
        raise FileNotFoundError("page not found: %s" % (page_dir / "index.html"))
    if not (style_dir / "style.css").is_file():
        raise FileNotFoundError("style not found: %s" % (style_dir / "style.css"))
    out_dir = Path(out_dir)
    shutil.copytree(page_dir, out_dir, dirs_exist_ok=True)
    shutil.copy2(style_dir / "style.css", out_dir / "style.css")
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    html = _set_link_href(html, "sp-style", "style.css")
    if layout and (style_dir / "layout.css").is_file():
        shutil.copy2(style_dir / "layout.css", out_dir / "layout.css")
        html = _set_link_href(html, "sp-layout", "layout.css")
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return out_dir / "index.html"


def render_page(
    workspace: Path, slug: str, style_id: str, out_png: Path, layout: bool = True, width: int = 1280
) -> Path:
    out_png = Path(out_png)
    out_png.unlink(missing_ok=True)  # never leave a stale PNG to be mistaken for this render
    with tempfile.TemporaryDirectory(prefix="design-refine-") as tmp:
        page = build_styled_copy(workspace, slug, style_id, Path(tmp) / "copy", layout=layout)
        ok = screenshot(page.resolve().as_uri(), out_png, width=width, untrusted=True, full_page=True)
    if not ok:
        raise RuntimeError("screenshot failed for page %s with style %s" % (slug, style_id))
    if not out_png.is_file() or out_png.stat().st_size == 0:
        raise RuntimeError("screenshot reported success but wrote no PNG: %s" % out_png)
    return out_png


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="render.py")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--style", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--no-layout", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    args = parser.parse_args(argv)  # argparse exits 2 on usage errors
    if os.environ.get(FORCE_NO_BROWSER_ENV) == "1" or not playwright_available():
        sys.stderr.write("Playwright is not available\n")
        return EXIT_NO_PLAYWRIGHT
    try:
        out = render_page(
            Path(args.workspace), args.slug, args.style, Path(args.out),
            layout=not args.no_layout, width=args.width,
        )
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
        sys.stderr.write("render failed: %s\n" % " ".join(str(e).split()))
        return EXIT_FAILED
    sys.stdout.write("%s\n" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
