from __future__ import annotations

import json

import pytest

from validate_style import find_forbidden_layout_rules, find_remote_urls, validate_style

TOKENS = {k: {} for k in ("palette", "fonts", "scale", "spacing", "radii", "shadows")}


def make_style(tmp_path, css="a { color: red }", layout=None, tokens=TOKENS):
    d = tmp_path / "style"
    d.mkdir()
    (d / "style.css").write_text(css, encoding="utf-8")
    if layout is not None:
        (d / "layout.css").write_text(layout, encoding="utf-8")
    if tokens is not None:
        text = tokens if isinstance(tokens, str) else json.dumps(tokens)
        (d / "tokens.json").write_text(text, encoding="utf-8")
    return d


def codes(problems):
    return [p.code for p in problems]


def test_remote_forms():
    css = """
    @font-face { src: url(http://a/b.woff); }
    a { background: url("//cdn/x.png"); }
    b { background: url('https://f/y.png'); }
    @import "https://f/a.css";
    @import url(https://f/b.css);
    """
    assert len(find_remote_urls(css)) == 5
    assert find_remote_urls("a{background:url(data:image/png;base64,AAA)}") == []
    assert find_remote_urls("@font-face{src:url(assets/f.woff2)}") == []
    assert find_remote_urls("/* url(http://x/y) */ a{color:red}") == []


@pytest.mark.parametrize(
    "decl, code",
    [
        ("display: none", "layout-hides"),
        ("DISPLAY:NONE", "layout-hides"),
        ("display : none !important", "layout-hides"),
        ("visibility: hidden", "layout-hides"),
        ("order: 2", "layout-reorders"),
        ("flex-direction: row-reverse", "layout-reorders"),
        ("flex-direction: column-reverse", "layout-reorders"),
        ("flex-flow: row-reverse wrap", "layout-reorders"),
        ("flex-flow: wrap column-reverse", "layout-reorders"),
        ("grid-area: a", "layout-reorders"),
        ("grid-row: 1", "layout-reorders"),
        ("grid-column: 2 / 3", "layout-reorders"),
        ("grid-template-areas: 'a b'", "layout-reorders"),
        ("grid-row-start: 2", "layout-reorders"),
        ("grid-row-end: 3", "layout-reorders"),
        ("grid-column-start: 2", "layout-reorders"),
        ("grid-column-end: 3", "layout-reorders"),
        ("grid-template: 'a b' / 1fr 1fr", "layout-reorders"),
    ],
)
def test_layout_rejects(decl, code):
    assert codes(find_forbidden_layout_rules(".x { %s }" % decl)) == [code]


@pytest.mark.parametrize(
    "decl",
    [
        "grid-row-gap: 1px",
        "grid-column-gap: 1px",
        "grid-template-columns: 1fr 1fr",
        "grid-template-rows: auto",
        "grid-auto-flow: row",
        "gap: 4px",
        "border-radius: 4px",
        "border: 1px solid red",
    ],
)
def test_layout_allows_related_properties(decl):
    assert find_forbidden_layout_rules(".x { %s }" % decl) == []


def test_layout_allows_and_tolerates_odd_input():
    assert find_forbidden_layout_rules(".x { display:grid; flex-direction: row; gap: 1px; width: 10px }") == []
    assert find_forbidden_layout_rules(".x { /* display:none */ color: red }") == []
    assert find_forbidden_layout_rules(".x { border-order: 1; display: none-ish }") == []
    assert codes(find_forbidden_layout_rules("@media (min-width: 1px) { .x { display: none } }")) == ["layout-hides"]
    find_forbidden_layout_rules(".x { display: none")  # unclosed brace must not crash
    find_forbidden_layout_rules("}}{{ @import")


def test_style_dir_requires_files(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert codes(validate_style(d)) == ["missing-file", "missing-file"]

    d = make_style(tmp_path, tokens=None)
    assert codes(validate_style(d)) == ["missing-file"]


@pytest.mark.parametrize(
    "tokens",
    ["not json {", "[]", '"x"', json.dumps({"palette": {}}), "{}"],
)
def test_bad_tokens(tmp_path, tokens):
    d = make_style(tmp_path, tokens=tokens)
    assert codes(validate_style(d)) == ["bad-tokens"]


def test_remote_and_layout_problems_reported(tmp_path):
    d = make_style(
        tmp_path,
        css="a { background: url(https://x/y.png) }",
        layout=".n { display: none; order: 1 } @import 'http://z/a.css';",
    )
    assert sorted(codes(validate_style(d))) == ["layout-hides", "layout-reorders", "remote-url", "remote-url"]


def test_complete_style_is_clean(tmp_path):
    d = make_style(tmp_path, layout=".n { display: grid; gap: 4px }")
    assert validate_style(d) == []
    d2 = tmp_path / "other"
    d2.mkdir()
    # layout.css is optional
    (d2 / "style.css").write_text("a{color:red}", encoding="utf-8")
    (d2 / "tokens.json").write_text(json.dumps(TOKENS), encoding="utf-8")
    assert validate_style(d2) == []
