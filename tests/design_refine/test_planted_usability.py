import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "planted_usability"
CRITIC = HERE.parents[1] / "skills" / "design-refine" / "critic.md"
PAGE = (FIXTURE / "pages" / "profile" / "index.html").read_text()
CSS = (FIXTURE / "styles" / "plain" / "style.css").read_text()


def _rule(selector):
    return re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS).group(1)


def test_critic_names_every_row_the_fixture_plants():
    text = CRITIC.read_text()
    for row in ("1.4.10 Reflow", "1.4.12 Text Spacing", "2.4.2 Page Titled", "2.5.5 Target Size", "4.1.3 Status Messages"):
        assert row in text, row


def test_fixture_plants_one_defect_per_new_row():
    assert "width: 1100px" in _rule('[data-sp="shell"]') and "@media" not in CSS
    card = _rule('[data-sp="card"]')
    assert "overflow: hidden" in card and "height: 96px" in card and "line-height: 24px !important" in card
    assert "<title>Page</title>" in PAGE
    assert "font-size: 11px" in _rule('[data-sp="dismiss"]')
    toast = re.search(r'<div data-sp="toast"[^>]*>', PAGE).group(0)
    assert "role=" not in toast and "aria-live" not in toast


def test_fixture_keeps_the_existing_rows_clean():
    assert "outline" not in CSS
    assert 'for="n"' in PAGE and 'for="e"' in PAGE
