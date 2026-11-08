from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

TOKEN_KEYS = ("palette", "fonts", "scale", "spacing", "radii", "shadows")


def make_workspace(
    root: Path,
    pages: List[Tuple[str, str]] = [("home", "Home")],
    styles: List[Tuple[str, Optional[str], bool]] = [("plain", None, False)],
) -> Path:
    """Build a workspace under root. pages: (slug, title); styles: (id, name_txt_or_None, has_layout)."""
    root = Path(root)
    for slug, title in pages:
        page_dir = root / "pages" / slug
        page_dir.mkdir(parents=True)
        (page_dir / "index.html").write_text(
            "<!DOCTYPE html>\n<html><head><title>%s</title>"
            '<link id="sp-style" rel="stylesheet" href="">'
            '<link id="sp-layout" rel="stylesheet" href="">'
            "</head><body></body></html>\n" % title,
            encoding="utf-8",
        )
    for style_id, name_txt, has_layout in styles:
        style_dir = root / "styles" / style_id
        style_dir.mkdir(parents=True)
        (style_dir / "tokens.json").write_text(json.dumps({k: {} for k in TOKEN_KEYS}), encoding="utf-8")
        (style_dir / "style.css").write_text("a{color:red}", encoding="utf-8")
        if has_layout:
            (style_dir / "layout.css").write_text(".x{margin:0}", encoding="utf-8")
        if name_txt is not None:
            (style_dir / "name.txt").write_text(name_txt, encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root
