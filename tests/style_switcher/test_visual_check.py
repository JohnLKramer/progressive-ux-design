from __future__ import annotations

import pytest

from acceptance import run_acceptance
from fixtures.make_workspace import make_workspace
from screenshot import playwright_available
from visual_check import evaluate_visual


def rect(top, bottom, left=0, right=10):
    return {"top": top, "bottom": bottom, "left": left, "right": right}


def measure(**overrides):
    base = {"vw": 1280, "docWidth": 1280, "cards": [], "duplicates": [], "bullets": 0, "bulletSample": "", "sidebars": []}
    base.update(overrides)
    return base


def codes(problems):
    return [p.split(":")[0] for p in problems]


def test_clean_measure_has_no_problems():
    assert evaluate_visual(measure(), layout_applied=True) == []


def test_card_whose_parts_share_a_row_is_clean():
    card = {"parts": [rect(0, 40), rect(5, 35), rect(10, 30), rect(0, 40)]}
    assert evaluate_visual(measure(cards=[card]), layout_applied=True) == []


def test_card_whose_parts_stack_fails_when_layout_applied():
    card = {"parts": [rect(0, 20), rect(20, 40), rect(40, 60)]}
    assert codes(evaluate_visual(measure(cards=[card]), layout_applied=True)) == ["card-not-one-row"]


def test_stacked_card_is_fine_without_layout():
    card = {"parts": [rect(0, 20), rect(20, 40), rect(40, 60)]}
    assert evaluate_visual(measure(cards=[card]), layout_applied=False) == []


def test_duplicate_nodes_fail_in_any_mode():
    problems = evaluate_visual(measure(duplicates=["Upcoming Past Favorites"]), layout_applied=False)
    assert codes(problems) == ["duplicate-nodes"]
    assert "Upcoming Past Favorites" in problems[0]


def test_bullets_fail_in_any_mode():
    problems = evaluate_visual(measure(bullets=3, bulletSample="Gifts"), layout_applied=False)
    assert codes(problems) == ["bullets"]
    assert "Gifts" in problems[0]


def test_sidebar_at_forty_percent_fails_only_with_layout():
    wide = {"width": 512}
    assert codes(evaluate_visual(measure(sidebars=[wide]), layout_applied=True)) == ["sidebar-too-wide"]
    assert evaluate_visual(measure(sidebars=[{"width": 511}]), layout_applied=True) == []
    assert evaluate_visual(measure(sidebars=[wide]), layout_applied=False) == []


def test_horizontal_overflow_fails():
    assert codes(evaluate_visual(measure(docWidth=1400), layout_applied=True)) == ["horizontal-overflow"]
    assert evaluate_visual(measure(docWidth=1281), layout_applied=True) == []


needs_browser = pytest.mark.skipif(not playwright_available(), reason="Playwright is not importable")

GOOD_CSS = """
[data-sp="card-list"], [data-sp="card-list"] > li, [data-sp="nav"] ul, [data-sp="nav"] li { list-style: none; margin: 0; padding: 0; }
[hidden] { display: none !important; }
"""
LIST_PAGE = (
    '<nav data-sp="nav"><ul><li>One</li><li>Two</li></ul></nav>'
    '<ul data-sp="card-list"><li><section data-sp="card"><p>a</p></section></li></ul>'
)


def _ws(tmp_path, body, css, layout_css=None):
    ws = make_workspace(tmp_path / "ws", pages=[("home", "Home")], styles=[("bold", "Bold", layout_css is not None)])
    index = ws / "pages" / "home" / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("<body></body>", "<body>%s</body>" % body), encoding="utf-8")
    (ws / "styles" / "bold" / "style.css").write_text(css, encoding="utf-8")
    if layout_css is not None:
        (ws / "styles" / "bold" / "layout.css").write_text(layout_css, encoding="utf-8")
    (ws / "styles" / "bold" / "notes.md").write_text("notes", encoding="utf-8")
    return ws


@needs_browser
def test_acceptance_fails_on_bullets(tmp_path, capsys):
    ws = _ws(tmp_path, LIST_PAGE, "a{color:red}")
    assert run_acceptance(ws, tmp_path / "out") != 0
    captured = capsys.readouterr()
    assert "bullets" in captured.out + captured.err


@needs_browser
def test_acceptance_fails_on_visible_duplicate_nav(tmp_path, capsys):
    page = '<nav data-sp="nav"><ul><li>Upcoming</li><li>Past</li></ul></nav><nav data-sp="nav"><ul><li>Upcoming</li><li>Past</li></ul></nav>'
    ws = _ws(tmp_path, page, GOOD_CSS)
    assert run_acceptance(ws, tmp_path / "out") != 0
    captured = capsys.readouterr()
    assert "duplicate-nodes" in captured.out + captured.err


@needs_browser
def test_acceptance_accepts_hidden_duplicate_nav(tmp_path):
    page = '<nav data-sp="nav"><ul><li>Upcoming</li><li>Past</li></ul></nav><nav data-sp="nav" hidden><ul><li>Upcoming</li><li>Past</li></ul></nav>'
    ws = _ws(tmp_path, page, GOOD_CSS)
    assert run_acceptance(ws, tmp_path / "out") == 0


@needs_browser
def test_acceptance_fails_on_stacked_card_parts_and_wide_sidebar(tmp_path, capsys):
    body = (
        '<div class="x"><div data-sp="content">c</div><div data-sp="sidebar">s</div></div>'
        '<ul data-sp="card-list"><li><section data-sp="card">'
        '<div data-sp="part" data-sp-variant="time">t</div><div data-sp="part" data-sp-variant="main">m</div>'
        '<div data-sp="part" data-sp-variant="action">a</div></section></li></ul>'
    )
    layout = ".x { display: flex; } .x > [data-sp=sidebar] { flex: 0 0 60%; }"
    ws = _ws(tmp_path, body, GOOD_CSS, layout_css=layout)
    assert run_acceptance(ws, tmp_path / "out") != 0
    text = "".join(capsys.readouterr())
    assert "card-not-one-row" in text
    assert "sidebar-too-wide" in text
