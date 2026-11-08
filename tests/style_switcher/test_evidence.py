from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

import gather_evidence
from gather_evidence import EvidenceError, gather_evidence as gather, write_evidence

FIXTURE = Path(__file__).parent / "fixtures" / "style_source"
SCRIPT = Path(gather_evidence.__file__)


def by_value(entries):
    return {e["value"]: e for e in entries}


def make_source(root: Path, pages: dict, files: dict = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (root / name).write_text(text, encoding="utf-8")
    for name, data in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return root


def page_with(css_href: str = "", inline: str = "") -> str:
    link = '<link rel="stylesheet" href="%s">' % css_href if css_href else ""
    return "<html><head>%s<style>%s</style></head><body><p>x</p></body></html>" % (link, inline)


@pytest.fixture
def fixture_copy(tmp_path):
    """Fixture copied to tmp_path/deep/src so `../../etc/passwd.css` lands in tmp_path/etc."""
    src = tmp_path / "deep" / "src"
    shutil.copytree(FIXTURE, src)
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "passwd.css").write_text(".leak{color:#123456}", encoding="utf-8")
    return src


def test_shared_color_counts_both_pages(fixture_copy):
    ev = gather(fixture_copy)
    assert ev["pages"] == ["page_a.html", "page_b.html"]
    color = by_value(ev["colors"])["#ff5500"]
    assert color["pages"] == 2
    # --brand, #f50, rgb(), hsl() in page A's sheet + inline hex; inline #FF5500 in page B
    assert color["count"] == 6


def test_normalization_merges_forms(fixture_copy):
    colors = by_value(gather(fixture_copy)["colors"])
    assert "#f50" not in colors and "#FF5500" not in colors
    assert colors["#112233"]["pages"] == 1
    assert colors["#000000"]["count"] == 1  # rgba(0,0,0,.2) drops alpha


def test_custom_properties_listed(fixture_copy):
    ev = gather(fixture_copy)
    assert ev["custom_properties"] == {"--brand": "#ff5500", "--space": "8px"}
    assert ev["custom_properties_total"] == 2


def test_font_file_listed_under_assets(fixture_copy):
    ev = gather(fixture_copy)
    assert ev["assets"]["fonts"] == ["page_a_files/brand.woff2"]
    assert ev["assets"]["images"] == ["page_b_files/logo.png"]
    assert ev["assets_truncated"] == {"fonts": 0, "images": 0}


def test_fonts_sizes_radii_shadows_spacing(fixture_copy):
    ev = gather(fixture_copy)
    fonts = by_value(ev["fonts"])
    assert fonts["Brand Sans"]["count"] == 1
    assert fonts["@font-face Brand Sans"]["count"] == 1
    assert fonts["Georgia"]["pages"] == 1
    assert set(by_value(ev["font_sizes"])) == {"16px", "2rem", "1.5rem"}
    assert set(by_value(ev["radii"])) == {"4px", "8px"}
    assert set(by_value(ev["shadows"])) == {"0 1px 2px rgba(0,0,0,.2)"}
    spacing = by_value(ev["spacing"])
    assert set(spacing) == {"4px", "8px", "16px", "12px"}
    assert spacing["8px"]["count"] == 2  # inline margin token + body padding token; --space is not spacing
    assert "0" not in spacing and "auto" not in spacing


def test_keyframes_ignored_and_media_descended(fixture_copy):
    ev = gather(fixture_copy)
    colors = by_value(ev["colors"])
    assert "#abcdef" not in colors and "#fedcba" not in colors
    assert "99px" not in by_value(ev["spacing"])
    assert "12px" in by_value(ev["spacing"])  # inside @media


def test_remote_counted_not_fetched_and_traversal_skipped(fixture_copy):
    ev = gather(fixture_copy)
    assert ev["remote_stylesheets"] == 1
    assert "../../etc/passwd.css" in ev["skipped_css"]
    assert "#123456" not in by_value(ev["colors"])


def test_absolute_and_symlink_escapes_skipped(tmp_path):
    outside = tmp_path / "outside.css"
    outside.write_text(".o{color:#654321}", encoding="utf-8")
    src = make_source(
        tmp_path / "src",
        {
            "a.html": page_with("/etc/hosts.css"),
            "b.html": page_with("link.css"),
        },
    )
    os.symlink(str(outside), str(src / "link.css"))
    ev = gather(src)
    assert "#654321" not in by_value(ev["colors"])
    assert set(ev["skipped_css"]) == {"/etc/hosts.css", "link.css"}


def test_unlinked_stylesheet_not_counted_but_assets_listed(tmp_path):
    src = make_source(
        tmp_path / "src",
        {"a.html": page_with(inline=".a{color:#111111}")},
        {"orphan_files/x.css": ".o{color:#222222}", "orphan_files/f.ttf": b"\x00\x01"},
    )
    ev = gather(src)
    assert set(by_value(ev["colors"])) == {"#111111"}
    assert ev["assets"]["fonts"] == ["orphan_files/f.ttf"]


def test_shared_sheet_counts_every_linking_page(tmp_path):
    src = make_source(
        tmp_path / "src",
        {"a.html": page_with("s.css"), "b.html": page_with("s.css"), "c.html": page_with()},
        {"s.css": ".a{color:#abcabc}"},
    )
    entry = by_value(gather(src)["colors"])["#abcabc"]
    assert (entry["count"], entry["pages"]) == (2, 2)


def test_oversized_css_truncated_and_listed(tmp_path):
    head = ".a{color:#010203}\n"
    filler = "/*" + "x" * (5 * 1024 * 1024) + "*/"
    big = head + filler + "\n.b{color:#040506}\n"
    src = make_source(tmp_path / "src", {"p.html": page_with("p_files/big.css")}, {"p_files/big.css": big})
    ev = gather(src)
    colors = by_value(ev["colors"])
    assert "#010203" in colors and "#040506" not in colors
    assert ev["truncated_css"] == ["p_files/big.css"]


def test_non_utf8_css_survives(tmp_path):
    css = b".a{color:#abcdef;font-family:\xff\xfeBad,serif}\n.b{font-size:12px}"
    src = make_source(tmp_path / "src", {"p.html": page_with("s.css")}, {"s.css": css})
    ev = gather(src)
    assert "#abcdef" in by_value(ev["colors"])
    assert "12px" in by_value(ev["font_sizes"])
    assert ev["truncated_css"] == []


def test_caps_and_custom_property_total(tmp_path):
    colors = "".join(".c%d{color:#%06x}" % (i, i + 1) for i in range(40))
    props = ":root{" + "".join("--p%03d:%dpx;" % (i, i) for i in range(300)) + "}"
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=colors + props)})
    ev = gather(src, top_n=5)
    assert len(ev["colors"]) == 5
    assert [e["value"] for e in ev["colors"]] == ["#000001", "#000002", "#000003", "#000004", "#000005"]
    full = gather(src)
    assert len(full["colors"]) == 25
    assert len(full["custom_properties"]) == 200
    assert full["custom_properties_total"] == 300
    assert list(full["custom_properties"]) == sorted(full["custom_properties"])


def test_values_truncated_to_120_chars(tmp_path):
    long_shadow = "0 0 " + "1px " * 100 + "#000"
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=".a{box-shadow:%s;--v:%s}" % (long_shadow, "y" * 500))})
    ev = gather(src)
    assert all(len(e["value"]) <= 120 for e in ev["shadows"])
    assert len(ev["custom_properties"]["--v"]) == 120


def test_assets_capped(tmp_path):
    files = {"p_files/f%03d.png" % i: b"x" for i in range(130)}
    src = make_source(tmp_path / "src", {"p.html": page_with()}, files)
    ev = gather(src)
    assert len(ev["assets"]["images"]) == 100
    assert ev["assets_truncated"] == {"fonts": 0, "images": 30}


def test_two_runs_identical_json(fixture_copy, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_evidence(fixture_copy, a)
    write_evidence(fixture_copy, b)
    assert a.read_bytes() == b.read_bytes()
    text = a.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert json.loads(text)["pages"] == ["page_a.html", "page_b.html"]


def test_deterministic_across_directory_order(fixture_copy, monkeypatch, tmp_path):
    a = tmp_path / "a.json"
    write_evidence(fixture_copy, a)
    real_walk = os.walk

    def reversed_walk(top, *args, **kwargs):
        for current, dirs, files in real_walk(top, *args, **kwargs):
            dirs.reverse()
            files.reverse()
            yield current, dirs, files

    monkeypatch.setattr(os, "walk", reversed_walk)
    b = tmp_path / "b.json"
    write_evidence(fixture_copy, b)
    assert a.read_bytes() == b.read_bytes()


def test_no_raw_html_or_absolute_paths_in_output(fixture_copy, tmp_path):
    out = tmp_path / "e.json"
    write_evidence(fixture_copy, out)
    text = out.read_text(encoding="utf-8")
    assert "SECRET_SCRIPT_MARKER" not in text
    assert "<script" not in text and "<h1" not in text and "<style" not in text
    assert str(tmp_path) not in text
    assert str(FIXTURE) not in text


def test_hundred_thousand_rules_stay_small_and_fast(tmp_path):
    rules = "".join(".r%d{color:#%06x;margin:%dpx;font-size:%dpx}\n" % (i, i, i, i % 97) for i in range(100_000))
    src = make_source(tmp_path / "src", {"p.html": page_with("p_files/big.css")}, {"p_files/big.css": rules})
    out = tmp_path / "e.json"
    start = time.monotonic()
    write_evidence(src, out)
    elapsed = time.monotonic() - start
    assert out.stat().st_size < 60 * 1024
    assert elapsed < 15, elapsed


def test_data_urls_and_braces_in_strings_do_not_confuse_parser(tmp_path):
    css = (
        ".a{background:url(\"data:image/svg+xml;utf8,<svg>{;}</svg>\");color:#aa0000}"
        '.b::after{content:"};}";color:#00aa00}'
    )
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=css)})
    assert set(by_value(gather(src)["colors"])) == {"#aa0000", "#00aa00"}


def test_transparent_and_named_colors(tmp_path):
    css = ".a{color:rgba(1,2,3,0);background:transparent;border-color:RebeccaPurple;outline:2px solid red;" \
          "fill:hsla(0,100%,50%,.5);color:#12345600;border-top-color:rgb(100% 0% 0% / 50%)}"
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=css)})
    colors = by_value(gather(src)["colors"])
    assert set(colors) == {"#663399", "#ff0000"}
    assert colors["#ff0000"]["count"] == 3


def test_empty_directory_raises(tmp_path):
    with pytest.raises(EvidenceError):
        write_evidence(tmp_path, tmp_path / "e.json")
    with pytest.raises(EvidenceError):
        gather(tmp_path / "missing")


def test_oversize_json_raises_after_shrinking(fixture_copy, tmp_path, monkeypatch):
    monkeypatch.setattr(gather_evidence, "MAX_JSON_BYTES", 100)
    with pytest.raises(EvidenceError, match="over the 100 byte limit"):
        write_evidence(fixture_copy, tmp_path / "e.json")
    assert not (tmp_path / "e.json").exists()


def test_shrinks_top_n_before_failing(tmp_path, monkeypatch):
    colors = "".join(".c%d{color:#%06x}" % (i, i + 1) for i in range(200))
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=colors)})
    full_size = len(json.dumps(gather(src), indent=2))
    monkeypatch.setattr(gather_evidence, "MAX_JSON_BYTES", full_size - 500)
    out = tmp_path / "e.json"
    write_evidence(src, out)
    assert len(json.loads(out.read_text(encoding="utf-8"))["colors"]) < 25


def run_cli(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT)] + [str(a) for a in args],
                          capture_output=True, text=True)


def test_cli_writes_evidence(fixture_copy, tmp_path):
    out = tmp_path / "e.json"
    result = run_cli(fixture_copy, out, "--top-n", "3")
    assert result.returncode == 0, result.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["colors"]) == 3


@pytest.mark.parametrize("args", [[], ["only-one"], ["a", "b", "--top-n"], ["a", "b", "--top-n", "x"],
                                  ["a", "b", "--top-n", "0"], ["a", "b", "--bogus"]])
def test_cli_usage_errors_exit_2(args):
    result = run_cli(*args)
    assert result.returncode == 2
    assert len(result.stderr.strip().splitlines()) == 1


def test_cli_failure_exits_1(tmp_path):
    result = run_cli(tmp_path, tmp_path / "e.json")
    assert result.returncode == 1
    assert len(result.stderr.strip().splitlines()) == 1
    assert result.stderr.startswith("error:")


# ---- fix round 1: linear scanning, bounded strings, parser details -------------------

HOSTILE_LIMIT_SECONDS = 5


def _timed_gather(src):
    start = time.perf_counter()
    ev = gather(src)
    elapsed = time.perf_counter() - start
    return ev, elapsed


def _hostile_css():
    return {
        "unclosed_url": "url(" * 250_000,
        "unclosed_comment": "/*a" * 1_700_000,
        "unclosed_brace_rules": "a{" * 2_500_000,
        "nested_braces": "{" * 1_000_000,
        "one_huge_value": ".a{margin:" + "1px " * 250_000 + "}",
        "whitespace_value": ".a{margin:1px" + " " * 1_000_000 + "x}",
        "unclosed_quote": '"' * 1_000_000,
        "deep_at_rules": "@media{" * 10_000,
    }


@pytest.mark.parametrize("kind", sorted(_hostile_css()))
@pytest.mark.parametrize("mode", ["linked", "inline"])
def test_hostile_css_is_scanned_in_linear_time(tmp_path, kind, mode):
    css = _hostile_css()[kind]
    if mode == "linked":
        src = make_source(tmp_path / "src", {"p.html": page_with("s.css")}, {"s.css": css})
    else:
        src = make_source(tmp_path / "src", {"p.html": page_with(inline=css)})
    ev, elapsed = _timed_gather(src)
    assert elapsed < HOSTILE_LIMIT_SECONDS, elapsed
    out = tmp_path / "e.json"
    write_evidence(src, out)
    assert isinstance(json.loads(out.read_text(encoding="utf-8")), dict)
    assert ev["pages_total"] == 1


def test_well_formed_css_after_unclosed_url_and_comment_rules(tmp_path):
    css = ".a{background:url( a b );color:#111111}.b{background:url('x)y');color:#222222}" \
          "/* c */.c{color:#333333}/* unclosed .d{color:#444444}"
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=css)})
    assert set(by_value(gather(src)["colors"])) == {"#111111", "#222222", "#333333"}


def _assert_bounded(src, tmp_path, top_n=25):
    out = tmp_path / "e.json"
    start = time.perf_counter()
    write_evidence(src, out, top_n)
    assert time.perf_counter() - start < HOSTILE_LIMIT_SECONDS
    assert out.stat().st_size <= 60_000
    return json.loads(out.read_text(encoding="utf-8"))


def test_huge_custom_property_name_is_clipped(tmp_path):
    name = "--" + "a" * 100_000
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=":root{%s:#ff0000}" % name)})
    for top_n in (5, 25):
        data = _assert_bounded(src, tmp_path, top_n)
        (key,) = data["custom_properties"]
        assert len(key) == gather_evidence.MAX_STRING and key.endswith("…")


def test_many_long_custom_property_names_fit(tmp_path):
    props = "".join("--%s%d:#ff0000;" % ("n" * 2000, i) for i in range(300))
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=":root{%s}" % props)})
    data = _assert_bounded(src, tmp_path)
    assert all(len(k) <= gather_evidence.MAX_STRING for k in data["custom_properties"])
    assert data["custom_properties_total"] >= 1


def test_deep_long_page_path_is_clipped_from_the_left(tmp_path):
    parts = ["d" * 200 for _ in range(3)]
    page = "/".join(parts + ["p" * 100 + ".html"])
    src = make_source(tmp_path / "src", {}, {page: page_with()})
    data = _assert_bounded(src, tmp_path)
    (shown,) = data["pages"]
    assert len(shown) == gather_evidence.MAX_STRING
    assert shown.startswith("…") and shown.endswith("p" * 100 + ".html")


def test_huge_skipped_href_and_render_of_100k_strings_are_clipped(tmp_path):
    href = "x" * 100_000 + ".css"
    src = make_source(tmp_path / "src", {"p.html": page_with(href)})
    data = _assert_bounded(src, tmp_path)
    (shown,) = data["skipped_css"]
    assert len(shown) == gather_evidence.MAX_STRING and shown.endswith(".css")
    raw = gather_evidence._Raw()
    raw.pages = ["q" * 100_000]
    raw.truncated_css = {"t" * 100_000}
    raw.fonts = ["f" * 100_000 + "1.woff", "f" * 100_000 + "2.woff"]
    out = gather_evidence._render(raw, 5)
    assert all(len(s) <= gather_evidence.MAX_STRING for s in
               out["pages"] + out["truncated_css"] + out["assets"]["fonts"])


def test_thousands_of_long_asset_names_fit(tmp_path):
    files = {"p_files/%s%d.png" % ("a" * 200, i): b"x" for i in range(5000)}
    src = make_source(tmp_path / "src", {"p.html": page_with()}, files)
    data = _assert_bounded(src, tmp_path)
    assert all(len(s) <= gather_evidence.MAX_STRING for s in data["assets"]["images"])
    assert data["assets_truncated"]["images"] > 0


def _css_evidence(tmp_path, css):
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=css)})
    return gather(src)


def test_font_shorthand_tallies_size_and_first_family(tmp_path):
    ev = _css_evidence(tmp_path, ".a{font:italic small-caps bold 14px/1.5 \"Helvetica Neue\", Arial, sans-serif}"
                                 ".b{font:12px Georgia}.c{font:400 1.25rem / 2 Roboto,serif!important}")
    assert set(by_value(ev["font_sizes"])) == {"14px", "12px", "1.25rem"}
    assert set(by_value(ev["fonts"])) == {"Helvetica Neue", "Georgia", "Roboto"}


def test_font_shorthand_ignores_system_and_unparseable(tmp_path):
    ev = _css_evidence(tmp_path, ".a{font:caption}.b{font:menu}.c{font:inherit}.d{font:bold}"
                                 ".e{font:calc(1px + 2px) Foo}.f{font:12px}.g{font:bold bold bold bold bold bold 9px X}")
    assert ev["font_sizes"] == [] and ev["fonts"] == []


def test_vendor_prefixed_shadow_and_radius_counted(tmp_path):
    ev = _css_evidence(tmp_path, ".a{-webkit-box-shadow:0 1px 2px #000;-moz-box-shadow:0 2px 3px #000;"
                                 "-webkit-border-radius:4px;-moz-border-radius:6px;-ms-border-radius:8px}")
    assert set(by_value(ev["shadows"])) == {"0 1px 2px #000", "0 2px 3px #000"}
    assert set(by_value(ev["radii"])) == {"4px", "6px", "8px"}


def test_noise_values_ignored_in_radii_shadows_sizes_spacing(tmp_path):
    ev = _css_evidence(tmp_path, ".a{border-radius:0;border-top-left-radius:0px;border-radius:none;"
                                 "box-shadow:var(--tw-ring-shadow), var(--tw-shadow);box-shadow:none;box-shadow:0;"
                                 "font-size:0;font-size:0px;font-size:initial;font-size:var(--x);"
                                 "border-radius:unset;margin:0px 5px;border-radius:3px;font-size:13px}")
    assert set(by_value(ev["radii"])) == {"3px"}
    assert ev["shadows"] == []
    assert set(by_value(ev["font_sizes"])) == {"13px"}
    assert set(by_value(ev["spacing"])) == {"5px"}


def test_named_color_only_counts_as_whole_token_in_color_properties(tmp_path):
    ev = _css_evidence(tmp_path, ":root{--font:Red Hat;--c:red;--c2:Red !important;--shadow:0 0 blue}"
                                 ".a{font-family:Red Hat;content:red;margin:red;color:Red;"
                                 "background:white url(x.png);border-left:1px solid navy;"
                                 "animation-name:green;text-decoration:underline teal;transition:color 1s}")
    colors = by_value(ev["colors"])
    assert colors["#ff0000"]["count"] == 3  # --c, --c2, color:Red
    assert set(colors) == {"#ff0000", "#ffffff", "#000080"}


def test_custom_properties_cap_prefers_colors_then_lengths(tmp_path):
    flags = "".join("--ab-flag-%d:none;" % i for i in range(300))
    tokens = "".join("--tok-%d:#%06x;" % (i, i + 1) for i in range(5))
    lengths = "--len-a:8px;--len-b:1.5rem;--len-c:50%;"
    src = make_source(tmp_path / "src", {"p.html": page_with(inline=":root{%s%s%s}" % (flags, lengths, tokens))})
    ev = gather(src)
    props = ev["custom_properties"]
    assert ev["custom_properties_total"] == 308
    assert len(props) == 200
    assert all("--tok-%d" % i in props for i in range(5))
    assert all(k in props for k in ("--len-a", "--len-b", "--len-c"))
    assert list(props) == sorted(props)
    assert ev == gather(src)
