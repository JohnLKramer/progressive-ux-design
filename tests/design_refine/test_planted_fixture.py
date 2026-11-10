import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "skills" / "style-switcher" / "scripts" / "validate.py"
PLANTED = Path(__file__).resolve().parent / "fixtures" / "planted"
PAGE = PLANTED / "pages" / "booking" / "index.html"
PLAIN = PLANTED / "styles" / "plain"
BOLD = PLANTED / "styles" / "bold"


def validate(*args):
    return subprocess.run(
        [sys.executable, "-I", str(VALIDATE)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def luminance(hex_colour):
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    chans = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        chans.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chans[0] + 0.7152 * chans[1] + 0.0722 * chans[2]


def contrast(fg, bg):
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rule_body(css, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, "no rule for %s" % selector
    return match.group(1)


def decl(body, prop):
    match = re.search(r"(?<![-\w])" + re.escape(prop) + r"\s*:\s*([^;]+)", body)
    assert match, "no %s declaration" % prop
    return match.group(1).strip()


class _Tree(HTMLParser):
    """Collects (tag, attrs, parent_index) for every element."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs), self.stack[-1] if self.stack else None))
        if tag not in ("meta", "link", "input", "br", "img"):
            self.stack.append(len(self.nodes) - 1)

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()


def tree():
    t = _Tree()
    t.feed(PAGE.read_text(encoding="utf-8"))
    return t.nodes


def test_page_validates():
    result = validate("page", PAGE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_styles_validate():
    for style in (PLAIN, BOLD):
        result = validate("style", style)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == ""


def test_manifest_validates_and_lists_workspace():
    result = validate("manifest", PLANTED)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((PLANTED / "manifest.json").read_text(encoding="utf-8"))
    assert [p["slug"] for p in manifest["pages"]] == ["booking"]
    assert [s["id"] for s in manifest["styles"]] == ["bold", "plain"]


def test_planted_structural_facts_in_page():
    nodes = tree()
    buttons = [(i, n) for i, n in enumerate(nodes) if n[0] == "button"]
    assert len(buttons) == 6
    first_card = buttons[:3]
    assert [n[1]["data-action"] for _, n in first_card] == [
        "cancel-reservation", "add-to-calendar", "bring-a-friend"]
    assert len({n[2] for _, n in first_card}) == 1, "buttons must be siblings in one row"
    parent = nodes[first_card[0][1][2]]
    assert "data-sp" not in parent[1], "buttons must not be grouped in a role part"
    # Credit balance is an undifferentiated paragraph: no number/label split.
    credits = [n for n in nodes if n[1].get("data-el") == "El2"]
    assert len(credits) == 1
    children = [n for n in nodes if n[2] is not None and nodes[n[2]][1].get("data-el") == "El2"]
    assert [c[0] for c in children if c[0] != "h2"] == ["p"]
    assert not any(n[1].get("data-sp") == "price" for n in nodes)
    # Unfixable without a doc row: no studio element anywhere.
    html = PAGE.read_text(encoding="utf-8").lower()
    assert "studio" not in html
    assert not any(n[1].get("data-sp-variant") == "venue" for n in nodes)


def test_planted_style_facts_in_plain_css():
    css = (PLAIN / "style.css").read_text(encoding="utf-8")
    body = rule_body(css, "body")
    ratio = contrast(decl(body, "color"), decl(body, "background"))
    assert ratio < 4.5, "body contrast %.2f should be below 4.5" % ratio

    cancel = rule_body(css, '[data-action="cancel-reservation"]')
    calendar = rule_body(css, '[data-action="add-to-calendar"]')
    cancel_bg = decl(cancel, "background")
    assert luminance(cancel_bg) < 0.05, "cancel is a solid dark fill"
    assert decl(calendar, "background") in ("transparent", "none")
    assert "border" in calendar


def test_bold_style_has_no_planted_contrast_defect():
    css = (BOLD / "style.css").read_text(encoding="utf-8")
    body = rule_body(css, "body")
    assert contrast(decl(body, "color"), decl(body, "background")) >= 4.5
