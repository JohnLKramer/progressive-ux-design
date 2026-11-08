from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import finalize_style
from finalize_style import finalize_style as finalize
from problems import ValidationError
from validate_style import validate_style
from vocab import WRAPPERS, load_roles

SCRIPT = Path(finalize_style.__file__)
TOKENS = {"palette": {}, "fonts": {}, "scale": {}, "spacing": {}, "radii": {}, "shadows": {}}
FONT_CSS = "@font-face{font-family:X;src:url(assets/brand.woff2) format('woff2')}\nbody{color:#111}\n"
FONT_BYTES = b"\x00wOF2\xff\xfe binary"


ROLE_CSS = "".join('[data-sp="%s"]{margin:0}\n' % r for r in sorted(load_roles() | set(WRAPPERS))) + "[hidden]{display:none!important}\n"


def make_style(root: Path, css: str = "body{color:#111}\n", tokens=TOKENS, layout=None, roles=True) -> Path:
    style = root / "styles" / "demo"
    style.mkdir(parents=True)
    (style / "style.css").write_text((ROLE_CSS if roles else "") + css, encoding="utf-8")
    if tokens is not None:
        (style / "tokens.json").write_text(json.dumps(tokens), encoding="utf-8")
    if layout is not None:
        (style / "layout.css").write_text(layout, encoding="utf-8")
    return style


def make_source(root: Path, files=None) -> Path:
    src = root / "neon"
    src.mkdir()
    for name, data in (files if files is not None else {"page_files/brand.woff2": FONT_BYTES}).items():
        path = src / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return src


EVIDENCE = {"fonts": ["page_files/brand.woff2"], "images": []}


def codes(exc_info):
    return [p.code for p in exc_info.value.problems]


def test_copies_referenced_font(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    finalize(style, src, EVIDENCE)
    assert (style / "assets" / "brand.woff2").read_bytes() == FONT_BYTES


def test_writes_name_txt_from_source(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    finalize(style, src, EVIDENCE)
    assert (style / "name.txt").read_text(encoding="utf-8").strip() == "neon"


def test_explicit_name_wins(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    finalize(style, src, EVIDENCE, name="Neon Nights")
    assert (style / "name.txt").read_text(encoding="utf-8").strip() == "Neon Nights"


def test_existing_name_txt_untouched(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    original = b"Mine \xc3\xa9\r\n\n"
    (style / "name.txt").write_bytes(original)
    finalize(style, src, EVIDENCE)
    finalize(style, src, EVIDENCE, name="  Mine \xe9 ")
    assert (style / "name.txt").read_bytes() == original


def test_remote_url_raises(tmp_path):
    style = make_style(tmp_path, "body{background:url(https://x.test/a.png)}")
    with pytest.raises(ValidationError) as exc:
        finalize(style, make_source(tmp_path), EVIDENCE)
    assert "remote-url" in codes(exc)


def test_missing_tokens_raises(tmp_path):
    style = make_style(tmp_path, tokens=None)
    with pytest.raises(ValidationError) as exc:
        finalize(style, make_source(tmp_path), EVIDENCE)
    assert "missing-file" in codes(exc)


def test_references_in_layout_css_and_quoted_forms(tmp_path):
    files = {"a/one.png": b"1", "b/two.woff": b"2", "c/three.svg": b"3"}
    style = make_style(
        tmp_path,
        "a{background:url(\"assets/one.png\")}\n",
        layout="b{src:url( 'assets/two.woff' ) format('woff')}c{x:url(assets/three.svg)}\n",
    )
    src = make_source(tmp_path, files)
    ev = {"fonts": ["b/two.woff"], "images": ["a/one.png", "c/three.svg"]}
    finalize(style, src, ev)
    assert [(style / "assets" / n).read_bytes() for n in ("one.png", "two.woff", "three.svg")] == [b"1", b"2", b"3"]


def test_remote_and_data_urls_are_not_assets(tmp_path):
    style = make_style(tmp_path, "a{background:url(data:image/png;base64,AAAA)}\n")
    finalize(style, make_source(tmp_path), EVIDENCE)
    assert not (style / "assets").exists()


def test_ambiguous_basename_raises(tmp_path):
    files = {"x_files/brand.woff2": b"1", "y_files/brand.woff2": b"2"}
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path, files)
    ev = {"fonts": ["x_files/brand.woff2", "y_files/brand.woff2"], "images": []}
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, ev)
    assert codes(exc) == ["missing-file"]
    assert "assets/brand.woff2" in str(exc.value)
    assert not (style / "assets").exists()


def test_reference_not_in_evidence_raises(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, {"fonts": [], "images": []})
    assert codes(exc) == ["missing-file"]
    assert "assets/brand.woff2" in str(exc.value)


def test_basename_match_is_case_sensitive(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path, {"p/Brand.woff2": b"1"})
    with pytest.raises(ValidationError):
        finalize(style, src, {"fonts": ["p/Brand.woff2"], "images": []})


def test_dotdot_reference_rejected(tmp_path):
    (tmp_path / "secret.txt").write_text("s")
    style = make_style(tmp_path, "a{src:url(assets/../../secret.txt)}")
    with pytest.raises(ValidationError) as exc:
        finalize(style, make_source(tmp_path), {"fonts": [], "images": ["secret.txt"]})
    assert "bad-asset-path" in codes(exc)


def test_symlinked_source_file_escaping_rejected(tmp_path):
    outside = tmp_path / "outside.woff2"
    outside.write_bytes(b"secret")
    src = make_source(tmp_path, {})
    (src / "page_files").mkdir()
    os.symlink(outside, src / "page_files" / "brand.woff2")
    style = make_style(tmp_path, FONT_CSS)
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, EVIDENCE)
    assert "bad-asset-path" in codes(exc)
    assert not (style / "assets" / "brand.woff2").exists()


def test_missing_source_file_raises(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path, {"other.txt": b"x"})
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, EVIDENCE)
    assert codes(exc) == ["missing-file"]


def test_zip_source_without_source_dir_raises(tmp_path):
    zpath = tmp_path / "neon.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("page_files/brand.woff2", FONT_BYTES)
    style = make_style(tmp_path, FONT_CSS)
    with pytest.raises(ValidationError) as exc:
        finalize(style, zpath, EVIDENCE)
    assert "missing-file" in codes(exc)


def test_zip_source_with_source_dir(tmp_path):
    zpath = tmp_path / "neon.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("page_files/brand.woff2", FONT_BYTES)
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    (unpacked / "page_files").mkdir()
    (unpacked / "page_files" / "brand.woff2").write_bytes(FONT_BYTES)
    style = make_style(tmp_path, FONT_CSS)
    finalize(style, zpath, EVIDENCE, source_dir=unpacked)
    assert (style / "name.txt").read_text(encoding="utf-8").strip() == "neon"
    assert (style / "assets" / "brand.woff2").read_bytes() == FONT_BYTES


def test_zip_without_references_needs_no_source_dir(tmp_path):
    zpath = tmp_path / "neon.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("a.html", "<p>x</p>")
    style = make_style(tmp_path)
    finalize(style, zpath, EVIDENCE)
    assert (style / "name.txt").is_file()


def test_idempotent_rerun(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    finalize(style, src, EVIDENCE)
    finalize(style, src, EVIDENCE)
    assert (style / "assets" / "brand.woff2").read_bytes() == FONT_BYTES
    assert (style / "name.txt").read_text(encoding="utf-8").strip() == "neon"


def run_cli(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT)] + [str(a) for a in args],
                          capture_output=True, text=True)


def write_evidence(tmp_path, evidence=None):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"assets": evidence or EVIDENCE}), encoding="utf-8")
    return path


def test_cli_success(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    result = run_cli(style, src, "--evidence", write_evidence(tmp_path), "--name", "Neon")
    assert (result.returncode, result.stdout.strip(), result.stderr) == (0, "ok", "")
    assert (style / "assets" / "brand.woff2").read_bytes() == FONT_BYTES
    assert (style / "name.txt").read_text(encoding="utf-8").strip() == "Neon"


def test_cli_source_dir_for_zip(tmp_path):
    zpath = tmp_path / "neon.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("page_files/brand.woff2", FONT_BYTES)
    unpacked = make_source(tmp_path)
    style = make_style(tmp_path, FONT_CSS)
    result = run_cli(style, zpath, "--evidence", write_evidence(tmp_path), "--source-dir", unpacked)
    assert result.returncode == 0, result.stderr


def test_cli_validation_failure_exit_1(tmp_path):
    style = make_style(tmp_path, "body{background:url(http://x.test/a.png)}")
    result = run_cli(style, make_source(tmp_path), "--evidence", write_evidence(tmp_path))
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip().startswith("remote-url:")
    assert len(result.stderr.strip().splitlines()) == 1


def test_cli_bad_evidence_exit_1_one_line(tmp_path):
    style = make_style(tmp_path)
    bad = tmp_path / "evidence.json"
    bad.write_text("{not json", encoding="utf-8")
    result = run_cli(style, make_source(tmp_path), "--evidence", bad)
    assert result.returncode == 1
    assert len(result.stderr.strip().splitlines()) == 1
    result = run_cli(style, tmp_path / "neon", "--evidence", tmp_path / "nope.json")
    assert result.returncode == 1
    assert len(result.stderr.strip().splitlines()) == 1


@pytest.mark.parametrize("args", [
    [],
    ["only-one"],
    ["a", "b"],
    ["a", "b", "--evidence"],
    ["a", "b", "--evidence", "e", "--bogus", "x"],
    ["a", "b", "--evidence", "e", "extra"],
])
def test_cli_usage_exit_2(args):
    result = run_cli(*args)
    assert result.returncode == 2
    assert len(result.stderr.strip().splitlines()) == 1
    assert result.stdout == ""


# ---- asset resolution -------------------------------------------------------------------


def dup_source(tmp_path, a=b"same", b=b"same"):
    src = make_source(tmp_path, {"a_files/f.woff2": a, "b_files/f.woff2": b})
    ev = {"fonts": ["a_files/f.woff2", "b_files/f.woff2"], "images": []}
    return src, ev


def font_css(ref):
    return "@font-face{font-family:X;src:url(%s)}\n" % ref


def test_exact_evidence_path_wins_and_keeps_subdirectories(tmp_path):
    src, ev = dup_source(tmp_path, b"AAA", b"BBB")
    style = make_style(tmp_path, font_css("assets/b_files/f.woff2"))
    finalize(style, src, ev)
    assert (style / "assets" / "b_files" / "f.woff2").read_bytes() == b"BBB"
    assert not (style / "assets" / "f.woff2").exists()


def test_identical_duplicates_use_first_sorted(tmp_path):
    src, ev = dup_source(tmp_path)
    ev["fonts"].reverse()
    style = make_style(tmp_path, font_css("assets/f.woff2"))
    finalize(style, src, ev)
    assert (style / "assets" / "f.woff2").read_bytes() == b"same"


def test_differing_duplicates_name_every_candidate(tmp_path):
    src, ev = dup_source(tmp_path, b"AAA", b"BBB")
    style = make_style(tmp_path, font_css("assets/f.woff2"))
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, ev)
    assert codes(exc) == ["missing-file"]
    assert "ambiguous: write the reference as assets/<one of: a_files/f.woff2, b_files/f.woff2>" in str(exc.value)
    assert not (style / "assets").exists()


# ---- reference forms --------------------------------------------------------------------


@pytest.mark.parametrize("css,named", [
    ("a{background:url(/x.png)}", "/x.png"),
    ("a{background:url(../x.png)}", "../x.png"),
    ("a{background:url(x.png)}", "x.png"),
    ("a{background:url(images/x.png)}", "images/x.png"),
    ("a{background:url('file:///etc/hosts')}", "file:///etc/hosts"),
    ('@import "x.css";', "x.css"),
    ("@import url(x.css);", "x.css"),
    ('a{background:image-set("x.png" 1x)}', "x.png"),
    ("a{background:image-set(url(x.png) 1x)}", "x.png"),
    ("a{background:image-set(url(assets/ok.png) 1x, 'y.png' 2x)}", "y.png"),
    ("a{background:url()}", "empty"),
])
def test_non_assets_local_reference_is_bad_asset_path(tmp_path, css, named):
    style = make_style(tmp_path, css)
    ev = {"fonts": [], "images": ["ok.png"]}
    with pytest.raises(ValidationError) as exc:
        finalize(style, make_source(tmp_path, {"ok.png": b"1"}), ev)
    assert "bad-asset-path" in codes(exc)
    assert named in str(exc.value)


def test_dot_slash_assets_is_normalized(tmp_path):
    style = make_style(tmp_path, font_css("./assets/brand.woff2"))
    finalize(style, make_source(tmp_path), EVIDENCE)
    assert (style / "assets" / "brand.woff2").read_bytes() == FONT_BYTES


def test_image_set_strings_and_urls_are_copied(tmp_path):
    css = 'a{background:image-set("assets/a.png" 1x, url(assets/b.png) 2x)}\n'
    style = make_style(tmp_path, css)
    src = make_source(tmp_path, {"p/a.png": b"A", "p/b.png": b"B"})
    finalize(style, src, {"fonts": [], "images": ["p/a.png", "p/b.png"]})
    assert [(style / "assets" / n).read_bytes() for n in ("a.png", "b.png")] == [b"A", b"B"]


def test_strings_outside_image_set_are_not_references(tmp_path):
    style = make_style(tmp_path, 'a{content:"x.png";font-family:"Some Font"}\n')
    finalize(style, make_source(tmp_path), EVIDENCE)


def test_fragment_only_url_is_not_a_file(tmp_path):
    style = make_style(tmp_path, "a{filter:url(#blur)}\n")
    finalize(style, make_source(tmp_path), EVIDENCE)


def test_percent_encoded_reference_is_decoded_once(tmp_path):
    style = make_style(tmp_path, font_css("assets/a%20b.woff2"))
    src = make_source(tmp_path, {"p/a b.woff2": b"sp"})
    finalize(style, src, {"fonts": ["p/a b.woff2"], "images": []})
    assert (style / "assets" / "a b.woff2").read_bytes() == b"sp"


def test_percent_encoded_dotdot_rejected(tmp_path):
    style = make_style(tmp_path, font_css("assets/%2e%2e/x.woff2"))
    with pytest.raises(ValidationError) as exc:
        finalize(style, make_source(tmp_path), EVIDENCE)
    assert "bad-asset-path" in codes(exc)


def test_references_differing_only_by_case_rejected(tmp_path):
    style = make_style(tmp_path, "a{background:url(assets/A.png)}b{background:url(assets/a.png)}\n")
    src = make_source(tmp_path, {"A.png": b"1", "a.png": b"2"})
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, {"fonts": [], "images": ["A.png", "a.png"]})
    assert "bad-asset-path" in codes(exc)
    assert not (style / "assets").exists()


def test_copies_landing_on_same_path_case_insensitively_rejected(tmp_path):
    style = make_style(tmp_path, "a{background:url(assets/a%20b.png)}b{background:url('assets/A b.png')}\n")
    src = make_source(tmp_path, {"p/a b.png": b"1", "p/A b.png": b"2"})
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, {"fonts": [], "images": ["p/a b.png", "p/A b.png"]})
    assert "bad-asset-path" in codes(exc)


# ---- truncation -------------------------------------------------------------------------


def test_missing_reference_mentions_truncation(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, {"fonts": [], "images": []}, assets_truncated={"fonts": 0, "images": 7})
    assert codes(exc) == ["missing-file"]
    assert "truncated" in str(exc.value)


def test_missing_reference_without_truncation_does_not_mention_it(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, {"fonts": [], "images": []}, assets_truncated={"fonts": 0, "images": 0})
    assert "truncated" not in str(exc.value)


def test_cli_passes_assets_truncated_through(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    ev = tmp_path / "evidence.json"
    ev.write_text(json.dumps({"assets": {"fonts": [], "images": []},
                              "assets_truncated": {"fonts": 2, "images": 0}}), encoding="utf-8")
    result = run_cli(style, src, "--evidence", ev)
    assert result.returncode == 1
    assert "truncated" in result.stderr


# ---- symlinks and idempotent cleanup ----------------------------------------------------


def test_symlinked_assets_dir_refused(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    os.symlink(elsewhere, style / "assets")
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, EVIDENCE)
    assert "bad-asset-path" in codes(exc)
    assert list(elsewhere.iterdir()) == []


def test_symlink_inside_assets_refused(tmp_path):
    outside = tmp_path / "outside.woff2"
    outside.write_bytes(b"orig")
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    (style / "assets").mkdir()
    os.symlink(outside, style / "assets" / "brand.woff2")
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, EVIDENCE)
    assert "bad-asset-path" in codes(exc)
    assert outside.read_bytes() == b"orig"


def test_rerun_removes_files_no_longer_referenced(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    finalize(style, src, EVIDENCE)
    manifest = style / "assets" / ".finalized-assets"
    assert manifest.read_text(encoding="utf-8").split() == ["brand.woff2"]
    (style / "assets" / "mine.txt").write_text("keep", encoding="utf-8")
    (style / "style.css").write_text(ROLE_CSS + "body{color:#111}\n", encoding="utf-8")
    finalize(style, src, EVIDENCE)
    assert not (style / "assets" / "brand.woff2").exists()
    assert (style / "assets" / "mine.txt").read_text(encoding="utf-8") == "keep"
    assert not manifest.exists()


def test_rerun_keeps_still_referenced_and_manifest_in_sync(tmp_path):
    files = {"p/a.png": b"A", "p/b.png": b"B"}
    ev = {"fonts": [], "images": ["p/a.png", "p/b.png"]}
    style, src = make_style(tmp_path, "a{x:url(assets/a.png)}b{x:url(assets/b.png)}\n"), make_source(tmp_path, files)
    finalize(style, src, ev)
    (style / "style.css").write_text(ROLE_CSS + "a{x:url(assets/a.png)}\n", encoding="utf-8")
    finalize(style, src, ev)
    assert (style / "assets" / "a.png").is_file() and not (style / "assets" / "b.png").exists()
    assert (style / "assets" / ".finalized-assets").read_text(encoding="utf-8").split() == ["a.png"]


def test_unlisted_files_are_never_deleted(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    (style / "assets").mkdir()
    (style / "assets" / "mine.txt").write_text("keep", encoding="utf-8")
    finalize(style, src, EVIDENCE)
    (style / "style.css").write_text(ROLE_CSS, encoding="utf-8")
    finalize(style, src, EVIDENCE)
    assert (style / "assets" / "mine.txt").is_file()


def test_manifest_entry_escaping_assets_refused(tmp_path):
    outside = tmp_path / "victim.txt"
    outside.write_text("v", encoding="utf-8")
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    (style / "assets").mkdir()
    (style / "assets" / ".finalized-assets").write_text("../../../victim.txt\n", encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, EVIDENCE)
    assert "bad-asset-path" in codes(exc)
    assert outside.read_text(encoding="utf-8") == "v"


def test_style_with_manifest_still_validates(tmp_path):
    style, src = make_style(tmp_path, FONT_CSS), make_source(tmp_path)
    finalize(style, src, EVIDENCE)
    assert (style / "assets" / ".finalized-assets").is_file()
    assert validate_style(style) == []


# ---- name.txt ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_empty_name_is_rejected(tmp_path, bad):
    style, src = make_style(tmp_path), make_source(tmp_path)
    with pytest.raises(ValueError):
        finalize(style, src, EVIDENCE, name=bad)
    assert not (style / "name.txt").exists()


def test_different_name_than_existing_name_txt_fails_loudly(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    finalize(style, src, EVIDENCE, name="First")
    with pytest.raises(ValidationError) as exc:
        finalize(style, src, EVIDENCE, name="Second")
    assert codes(exc) == ["name-mismatch"]
    assert "First" in str(exc.value) and "Second" in str(exc.value)
    assert (style / "name.txt").read_text(encoding="utf-8").strip() == "First"


def test_same_name_again_is_fine(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    finalize(style, src, EVIDENCE, name="First")
    finalize(style, src, EVIDENCE, name=" First ")


def test_cli_empty_name_is_usage_error(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    result = run_cli(style, src, "--evidence", write_evidence(tmp_path), "--name", "  ")
    assert result.returncode == 2
    assert len(result.stderr.strip().splitlines()) == 1


def test_cli_name_mismatch_exit_1(tmp_path):
    style, src = make_style(tmp_path), make_source(tmp_path)
    ev = write_evidence(tmp_path)
    assert run_cli(style, src, "--evidence", ev, "--name", "A").returncode == 0
    result = run_cli(style, src, "--evidence", ev, "--name", "B")
    assert result.returncode == 1
    assert result.stderr.startswith("name-mismatch:")


# ---- lint_style -------------------------------------------------------------------------

CLEAN_TOKENS = {
    "palette": {"brand": "#7A1FA2"}, "fonts": {"body": '"Planted Sans", sans-serif'},
    "scale": {"lg": "1.25rem"}, "spacing": {"md": "16px"}, "radii": {"card": "14px"},
    "shadows": {"card": "0 6px 18px rgba(20, 10, 40, 0.25)"},
}
CLEAN_ROOT = (
    ":root{--color-brand:#7a1fa2;--font-body:\"Planted Sans\",   sans-serif;--size-lg:1.25rem;"
    "--space-md:16px;--radius-card:14px;--shadow-card:0 6px 18px RGBA(20, 10, 40, 0.25);}\n"
)


_lint_runs = iter(range(10 ** 6))


def lint_codes(tmp_path, css="", layout=None, tokens=CLEAN_TOKENS, roles=True):
    tmp_path = tmp_path / str(next(_lint_runs))
    tmp_path.mkdir()
    style = make_style(tmp_path, CLEAN_ROOT + css, tokens=tokens, layout=layout, roles=roles)
    return [p.code for p in finalize_style.lint_style(style)]


def test_clean_style_has_no_lint_problems(tmp_path):
    css = ("@font-face{font-family:'Planted Sans';src:url(assets/x.woff2);display:none}\n"
           "@keyframes k{from{display:none}to{display:block}}\n"
           "[hidden]{display:none}\nsvg{width:100%;max-width:2rem;height:auto}\n"
           "nav svg{width:20px}\n@media (min-width:1px){p{color:var(--color-brand)}}\n"
           "a{color:var(--missing, red)}\n")
    assert lint_codes(tmp_path, css) == []


@pytest.mark.parametrize("css", [
    "svg{width:24px}", "img{height:10px}", "*{width:5px}", "a, svg {width:1em}",
    "svg{height:0!important}", "@media (min-width:1px){svg{width:2px}}", "SVG{width:2px}",
])
def test_svg_global_size_flagged(tmp_path, css):
    assert "svg-global-size" in lint_codes(tmp_path, css)


@pytest.mark.parametrize("css", [
    "svg{width:100%}", "svg{width:auto;height:max-content}", "img{height:fit-content}",
    "svg{max-width:20px;max-height:20px}", "nav svg{width:20px}", "a svg{height:1em}",
    "button img{width:2px}", '[data-sp="card"] svg{width:20px}', "svg.icon{width:20px}",
    ".svg{width:2px}",
])
def test_svg_global_size_not_flagged(tmp_path, css):
    assert "svg-global-size" not in lint_codes(tmp_path, css)


@pytest.mark.parametrize("css", [
    "p{display:none}", "p{visibility:hidden}", ".a,[hidden]{display:none}",
    "@media (max-width:1px){.x{display: none !important}}", "p{DISPLAY:NONE}",
])
def test_style_hides_flagged(tmp_path, css):
    assert "style-hides" in lint_codes(tmp_path, css)


@pytest.mark.parametrize("css", [
    "[hidden]{display:none}", "[hidden]{visibility:hidden}", "@keyframes k{from{display:none}}",
    "@font-face{font-family:X;display:none}", "p{display:block;visibility:visible}",
])
def test_style_hides_not_flagged(tmp_path, css):
    assert "style-hides" not in lint_codes(tmp_path, css)


def test_style_hides_ignores_layout_css(tmp_path):
    assert "style-hides" not in lint_codes(tmp_path, layout="p{display:none}")


def test_undefined_var_flagged_in_style_and_layout(tmp_path):
    assert "undefined-var" in lint_codes(tmp_path, "p{color:var(--nope)}")
    assert "undefined-var" in lint_codes(tmp_path, layout="p{margin:var( --nope )}")


def test_undefined_var_names_the_variable(tmp_path):
    style = make_style(tmp_path, "p{color:var(--nope)}")
    problems = finalize_style.lint_style(style)
    assert [p.code for p in problems] == ["undefined-var"]
    assert "--nope" in problems[0].message


def test_defined_vars_and_fallbacks_are_fine(tmp_path):
    assert lint_codes(tmp_path, "p{color:var(--a)}", layout=":root{--a:red}") == []
    assert lint_codes(tmp_path, "p{--b:1;margin:var(--b)}") == []
    assert lint_codes(tmp_path, "p{color:var(--nope, red)}") == []


def test_token_var_flagged(tmp_path):
    tokens = dict(CLEAN_TOKENS, palette={"brand": "var(--color-brand)"})
    assert "token-var" in lint_codes(tmp_path, tokens=tokens)


def test_token_var_ignores_plain_strings(tmp_path):
    assert "token-var" not in lint_codes(tmp_path)


@pytest.mark.parametrize("section,var", [
    ("palette", "--color-brand"), ("fonts", "--font-body"), ("scale", "--size-lg"),
    ("spacing", "--space-md"), ("radii", "--radius-card"), ("shadows", "--shadow-card"),
])
def test_token_mismatch_missing_and_different(tmp_path, section, var):
    root = CLEAN_ROOT.replace(var + ":", "--other:")
    style = make_style(tmp_path, root, tokens=CLEAN_TOKENS)
    problems = finalize_style.lint_style(style)
    assert [p.code for p in problems] == ["token-mismatch"]
    assert var in problems[0].message


def test_token_mismatch_different_value(tmp_path):
    tokens = dict(CLEAN_TOKENS, spacing={"md": "20px"})
    style = make_style(tmp_path, CLEAN_ROOT, tokens=tokens)
    problems = finalize_style.lint_style(style)
    assert [p.code for p in problems] == ["token-mismatch"]
    assert "md" in problems[0].message


def test_token_mismatch_extra_root_vars_and_whitespace_case_are_fine(tmp_path):
    assert lint_codes(tmp_path, ":root{--extra:1}") == []


def test_token_mismatch_requires_root_selector(tmp_path):
    style = make_style(tmp_path, CLEAN_ROOT.replace(":root", "body"), tokens=CLEAN_TOKENS)
    assert "token-mismatch" in [p.code for p in finalize_style.lint_style(style)]


def test_token_mismatch_non_string_value(tmp_path):
    tokens = dict(CLEAN_TOKENS, scale={"lg": 16})
    assert "token-mismatch" in lint_codes(tmp_path, tokens=tokens)


def test_role_rule_missing_names_roles_and_wrappers(tmp_path):
    style = make_style(tmp_path, CLEAN_ROOT, tokens=CLEAN_TOKENS, roles=False)
    problems = [p for p in finalize_style.lint_style(style) if p.code == "role-rule-missing"]
    assert len(problems) == len(load_roles() | set(WRAPPERS))
    assert any("shell" in p.message for p in problems) and any("card" in p.message for p in problems)


@pytest.mark.parametrize("selector", ['[data-sp="card"]', "[data-sp='card']", "[data-sp=card]", "main [ data-sp = card ]:hover"])
def test_role_selector_quote_forms_accepted(tmp_path, selector):
    css = ROLE_CSS.replace('[data-sp="card"]', selector)
    style = make_style(tmp_path, CLEAN_ROOT, tokens=CLEAN_TOKENS, roles=False)
    (style / "style.css").write_text(CLEAN_ROOT + css, encoding="utf-8")
    assert [p for p in finalize_style.lint_style(style) if "card" in p.message] == []


def test_role_in_declaration_value_does_not_count(tmp_path):
    css = ROLE_CSS.replace('[data-sp="card"]{margin:0}', 'p{content:"[data-sp=card]"}')
    style = make_style(tmp_path, CLEAN_ROOT, tokens=CLEAN_TOKENS, roles=False)
    (style / "style.css").write_text(CLEAN_ROOT + css, encoding="utf-8")
    assert any(p.code == "role-rule-missing" and "card" in p.message for p in finalize_style.lint_style(style))


def hidden_codes(tmp_path, css):
    style = make_style(tmp_path, CLEAN_ROOT + css, tokens=CLEAN_TOKENS)
    text = (style / "style.css").read_text(encoding="utf-8").replace("[hidden]{display:none!important}\n", "")
    (style / "style.css").write_text(text + css, encoding="utf-8")
    return [p.code for p in finalize_style.lint_style(style) if p.code == "hidden-rule"]


def test_hidden_rule_missing_is_reported(tmp_path):
    assert hidden_codes(tmp_path, "") == ["hidden-rule"]


def test_hidden_rule_without_important_is_reported(tmp_path):
    assert hidden_codes(tmp_path, "[hidden]{display:none}\n") == ["hidden-rule"]


def test_hidden_rule_with_important_passes_even_after_a_plain_one(tmp_path):
    assert hidden_codes(tmp_path, "[hidden]{display:none}\n[hidden] { display: none !important; }\n") == []


def test_lint_tolerates_missing_files_and_bad_tokens(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert finalize_style.lint_style(empty) == []


def test_lint_tolerates_invalid_tokens_json(tmp_path):
    style = make_style(tmp_path, CLEAN_ROOT)
    (style / "tokens.json").write_text("{nope", encoding="utf-8")
    assert "token-mismatch" not in [p.code for p in finalize_style.lint_style(style)]


def test_lint_scanner_is_linear(tmp_path):
    import time
    css = "a{" * 40000 + "/*" * 1000 + "var(" * 20000 + "'" * 5000
    style = make_style(tmp_path, CLEAN_ROOT + css, tokens=CLEAN_TOKENS)
    start = time.monotonic()
    finalize_style.lint_style(style)
    assert time.monotonic() - start < 5


def test_finalize_raises_lint_and_validate_problems_together(tmp_path):
    style = make_style(tmp_path, "p{display:none;background:url(https://x.test/a.png)}", roles=False)
    with pytest.raises(ValidationError) as exc:
        finalize(style, make_source(tmp_path), EVIDENCE)
    assert {"remote-url", "style-hides", "role-rule-missing"} <= set(codes(exc))


def test_finalize_passes_a_clean_style(tmp_path):
    style = make_style(tmp_path, CLEAN_ROOT, tokens=CLEAN_TOKENS)
    finalize(style, make_source(tmp_path), EVIDENCE)
