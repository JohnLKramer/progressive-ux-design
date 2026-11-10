from __future__ import annotations

import json
from pathlib import Path

TOKEN_KEYS = ("palette", "fonts", "scale", "spacing", "radii", "shadows")

# Based on tests/style_switcher/fixtures/mockup.html, with the two style slots added so it
# passes `validate.py page`.
DEMO_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Class finder - demo</title>
<link id="sp-style" rel="stylesheet" href="">
<link id="sp-layout" rel="stylesheet" href="">
</head>
<body>
<header data-el="El1">
<h1>Class finder</h1>
<nav>
<a href="#" data-action="go-home" data-exit="home">Home</a>
<a href="#" data-action="go-bookings" data-exit="bookings">My bookings</a>
</nav>
</header>
<section class="hero" data-el="El2">
<h2>Find your next class</h2>
<button data-action="open-search" data-exit="search">Search classes</button>
</section>
<section data-el="El3">
<h2>Popular today</h2>
<ul>
<li data-el="El4"><h3>Morning Flow</h3><button data-action="book-class" data-exit="confirm" data-variant="primary">Book</button></li>
<li data-el="El5"><h3>Lunch Break Ride</h3><button data-action="book-class" data-exit="confirm">Book</button></li>
</ul>
</section>
</body>
</html>
"""


def make_workspace(tmp: Path) -> Path:
    """Build a workspace with pages/demo and styles a and b, all valid."""
    root = Path(tmp)
    page_dir = root / "pages" / "demo"
    page_dir.mkdir(parents=True)
    (page_dir / "index.html").write_text(DEMO_PAGE, encoding="utf-8")
    for style_id, color in (("a", "#123456"), ("b", "#654321")):
        style_dir = root / "styles" / style_id
        style_dir.mkdir(parents=True)
        (style_dir / "tokens.json").write_text(json.dumps({k: {} for k in TOKEN_KEYS}), encoding="utf-8")
        (style_dir / "style.css").write_text("body{color:%s}\n" % color, encoding="utf-8")
        (style_dir / "layout.css").write_text("section{margin:0 auto}\n", encoding="utf-8")
    return root
