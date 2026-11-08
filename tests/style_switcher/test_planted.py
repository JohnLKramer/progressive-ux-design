from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures.planted_acceptance import PLANTED_COLORS, check_planted_style
from gather_evidence import gather_evidence
from vocab import WRAPPERS, load_roles

FIXTURE = Path(__file__).parent / "fixtures" / "planted_style"
TOKENS = {
    "palette": {"brand": "#7A1FA2", "accent": "#ffb300", "teal": "#00897b", "surface": "#f4f1ea"},
    "fonts": {"body": "\"Planted Sans\", sans-serif"},
    "scale": {}, "spacing": {}, "radii": {}, "shadows": {},
}
FONT_FACE = "@font-face { font-family: 'Planted Sans'; src: url(assets/planted-sans.woff2) format('woff2'); }\n"
ROOT = ":root { --color-brand: #7a1fa2; --color-accent: #ffb300; --color-teal: #00897b; --color-surface: #f4f1ea; --font-body: \"Planted Sans\", sans-serif; }\n"


def build(root: Path, tokens=TOKENS, roles=None, css_extra="", font_face=FONT_FACE, font_file=True,
          name="Planted\n", notes="Notes.\n", quote_style=None) -> Path:
    style = root / "demo"
    style.mkdir()
    (style / "tokens.json").write_text(json.dumps(tokens), encoding="utf-8")
    roles = sorted(load_roles() | set(WRAPPERS)) if roles is None else roles
    forms = ["[data-sp=\"%s\"]", "main  [ data-sp = '%s' ]:hover, p", "[data-sp=%s]"]
    rules = "".join(
        (forms[i % 3] if quote_style is None else quote_style) % r + " { color: #111; }\n"
        for i, r in enumerate(roles)
    )
    (style / "style.css").write_text(ROOT + font_face + rules + "[hidden] { display: none !important; }\n" + css_extra, encoding="utf-8")
    if font_file:
        (style / "assets").mkdir()
        (style / "assets" / "planted-sans.woff2").write_bytes(b"wOF2")
    if name is not None:
        (style / "name.txt").write_text(name, encoding="utf-8")
    if notes is not None:
        (style / "notes.md").write_text(notes, encoding="utf-8")
    return style


def failures_of(style) -> str:
    return "\n".join(check_planted_style(style))


def test_passing_style(tmp_path):
    assert check_planted_style(build(tmp_path)) == []


def test_failing_style_reports_every_kind(tmp_path):
    tokens = dict(TOKENS, palette={"brand": "#7a1fa2"}, fonts={"body": "Arial"})
    roles = sorted(load_roles())[1:]
    style = build(tmp_path, tokens, roles, "a{background:url(https://x.test/a.png)}")
    failures = failures_of(style)
    assert "remote-url" in failures
    assert "#ffb300" in failures and "#00897b" in failures and "#f4f1ea" in failures
    assert "palette is missing planted color #7a1fa2" not in failures
    assert "Planted Sans" in failures
    assert "[data-sp=\"%s\"]" % sorted(load_roles())[0] in failures
    assert "remote URL" in failures


@pytest.mark.parametrize("value", ["rgb(0,0,0) #00897b", "#00897b80", "x#00897b", "#00897b #ffffff", "1px solid #00897b"])
def test_palette_substring_does_not_count(tmp_path, value):
    tokens = dict(TOKENS, palette=dict(TOKENS["palette"], teal=value))
    failures = [f for f in check_planted_style(build(tmp_path, tokens)) if f.startswith("palette")]
    assert failures == ["palette is missing planted color #00897b"]


def test_palette_whole_value_with_whitespace_and_case_counts(tmp_path):
    tokens = dict(TOKENS, palette=dict(TOKENS["palette"], teal="  #00897B \n"))
    assert [f for f in check_planted_style(build(tmp_path, tokens)) if f.startswith("palette")] == []


def test_unquoted_role_selector_is_accepted(tmp_path):
    assert check_planted_style(build(tmp_path, quote_style="[data-sp=%s]")) == []


def test_role_in_declaration_value_does_not_count(tmp_path):
    style = build(tmp_path, roles=[r for r in sorted(load_roles() | set(WRAPPERS)) if r != "card"],
                  css_extra="p { content: \"[data-sp='card']\"; }\n")
    assert any("\"card\"" in f for f in check_planted_style(style))


@pytest.mark.parametrize("font_face", [
    "",
    "@font-face { font-family: 'Other'; src: url(assets/planted-sans.woff2); }\n",
    "@font-face { font-family: 'Planted Sans'; src: url(assets/other.woff2); }\n",
    "@font-face { font-family: 'Planted Sans'; }\n",
    "p { font-family: 'Planted Sans'; src: url(assets/planted-sans.woff2); }\n",
])
def test_missing_or_wrong_font_face_fails(tmp_path, font_face):
    assert "@font-face" in failures_of(build(tmp_path, font_face=font_face))


@pytest.mark.parametrize("font_face", [
    "@font-face{font-family:\"Planted Sans\";src:url(\"./assets/planted-sans.woff2\") format(\"woff2\")}\n",
    "@font-face{src:url('assets/planted-sans.woff2');font-family:Planted Sans}\n",
])
def test_font_face_spellings_accepted(tmp_path, font_face):
    assert check_planted_style(build(tmp_path, font_face=font_face)) == []


def test_missing_font_file_fails(tmp_path):
    assert "planted-sans.woff2" in failures_of(build(tmp_path, font_file=False))


@pytest.mark.parametrize("kwargs,named", [
    ({"name": None}, "name.txt"), ({"name": " \n"}, "name.txt"),
    ({"notes": None}, "notes.md"), ({"notes": ""}, "notes.md"),
])
def test_missing_or_empty_name_and_notes_fail(tmp_path, kwargs, named):
    assert named in failures_of(build(tmp_path, **kwargs))


def test_lint_problems_are_reported(tmp_path):
    failures = failures_of(build(tmp_path, css_extra="p { display: none; color: var(--nope); }\n"))
    assert "lint_style: style-hides" in failures and "lint_style: undefined-var" in failures


def test_token_mismatch_is_reported(tmp_path):
    tokens = dict(TOKENS, spacing={"md": "16px"})
    assert "lint_style: token-mismatch" in failures_of(build(tmp_path, tokens))


def test_missing_files_fail(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert any("missing-file" in f for f in check_planted_style(empty))


def test_fixture_carries_planted_evidence():
    expected = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    ev = gather_evidence(FIXTURE)
    colors = {c["value"]: c for c in ev["colors"]}
    for color in expected["colors"]:
        assert color in colors and colors[color]["pages"] == 2 and colors[color]["count"] >= 4
    assert tuple(expected["colors"]) == PLANTED_COLORS
    fonts = {f["value"] for f in ev["fonts"]}
    assert {expected["font_family"], "@font-face " + expected["font_family"]} <= fonts
    assert ev["radii"][0]["value"] == expected["radius"]
    assert ev["shadows"][0]["value"] == expected["shadow"]
    assert ev["custom_properties"] == expected["custom_property"]
    assert ev["assets"]["fonts"] == [expected["font_file"]]
    assert (FIXTURE / expected["font_file"]).is_file()
    assert ev["remote_stylesheets"] == 0
