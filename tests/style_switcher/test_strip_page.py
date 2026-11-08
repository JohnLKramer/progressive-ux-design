from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import outline_page
from strip_page import StripError, strip_page as run_strip
from validate_page import validate_page

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "style-switcher" / "scripts"


@pytest.fixture
def source(tmp_path):
    """A copy of the saved-page fixture (html + `_files` sibling) in its own dir."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    shutil.copy(FIXTURES / "saved_page.html", src_dir / "saved_page.html")
    shutil.copytree(FIXTURES / "saved_page_files", src_dir / "saved_page_files")
    return src_dir / "saved_page.html"


@pytest.fixture
def stripped(source, tmp_path):
    dest = tmp_path / "dest"
    report = run_strip(source, dest)
    return report, dest, (dest / "index.html").read_text(encoding="utf-8")


def run_cli(script, *args):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPTS / script)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def test_stripped_page_validates_clean(stripped):
    report, dest, _ = stripped
    assert validate_page(dest / "index.html", set(report.source_el_ids)) == []


def test_source_el_ids_are_sorted_and_survive(stripped):
    report, _, out = stripped
    assert report.source_el_ids == ["El1", "El2", "El3", "El4"]
    assert 'data-el="El3"' in out


def test_visible_words_retained(stripped):
    report, _, _ = stripped
    assert report.words_after > 0
    assert report.words_after / report.words_before >= 0.9


def test_script_text_not_counted_as_words(tmp_path):
    src = tmp_path / "p.html"
    src.write_text("<p>one two</p><script>a b c d e f</script><noscript>x y z</noscript>", encoding="utf-8")
    report = run_strip(src, tmp_path / "d")
    assert (report.words_before, report.words_after) == (2, 2)


def test_local_image_is_localized(stripped):
    report, dest, out = stripped
    assert (dest / "assets" / "logo.png").is_file()
    assert report.localized == ["assets/logo.png"]
    assert 'src="assets/logo.png"' in out
    assert 'srcset="assets/logo.png 1x"' in out


def test_remote_references_removed_and_listed(stripped):
    report, _, out = stripped
    assert not re.search(r'(src|srcset|poster)="[^"]*(https?:|//)', out)
    for url in (
        "https://cdn.example.com/logo@2x.png",
        "https://cdn.example.com/poster.jpg",
        "https://cdn.example.com/clip.mp4",
        "https://ads.example.com/frame",
        "https://t.example.com/pixel.gif",
        "https://cdn.example.com/hero.jpg",
    ):
        assert url in report.removed_remote
    assert "<iframe" not in out and "<img src=\"https" not in out


def test_removed_scripts_counted(stripped):
    report, _, out = stripped
    assert report.removed_scripts == 3
    assert "<script" not in out and "<style" not in out and "<noscript" not in out


def test_links_replaced_by_two_hrefless_slots(stripped):
    _, _, out = stripped
    assert out.count("<link") == 2
    assert '<link id="sp-style" rel="stylesheet">' in out
    assert '<link id="sp-layout" rel="stylesheet">' in out
    assert "canonical" not in out and "preconnect" not in out


def test_head_is_created_when_missing(tmp_path):
    src = tmp_path / "p.html"
    src.write_text("<h1 data-el='a'>Hi there</h1>", encoding="utf-8")
    run_strip(src, tmp_path / "d")
    out = (tmp_path / "d" / "index.html").read_text(encoding="utf-8")
    assert "<head>" in out and 'id="sp-style"' in out
    assert validate_page(tmp_path / "d" / "index.html", {"a"}) == []


def test_no_class_style_handlers_or_comments(stripped):
    _, _, out = stripped
    assert "class=" not in out
    assert "style=" not in out
    assert not re.search(r"\son[a-z]+=", out)
    assert "<!--" not in out


def test_vendor_attributes_dropped_data_and_aria_kept(stripped):
    _, _, out = stripped
    assert "ng-app" not in out and "ng-click" not in out
    assert 'aria-label="Main"' in out
    assert 'data-vendor="y"' in out  # data-* is kept by contract


def test_ids_kept_only_where_referenced(stripped):
    _, _, out = stripped
    assert 'id="pricing"' in out  # #pricing href
    assert 'id="pricing-title"' in out  # aria-labelledby
    assert 'id="email"' in out  # label for
    for dead in ("site-header", "main-nav", "about-link", "unused-field", "page-footer", 'id="top"'):
        assert dead not in out


def test_entities_round_trip(stripped):
    _, _, out = stripped
    assert "Acme &amp; Co Pricing" in out
    assert "&amp; cancel any time" in out
    assert "Prices&nbsp;in USD" in out
    assert 'value="a&quot;b"' in out


def test_unclosed_tags_do_not_nest(stripped):
    _, _, out = stripped
    assert out.count("<li>") == 3
    assert "</li><li>" in out


def test_second_run_is_byte_identical_and_clears_stale_assets(source, tmp_path):
    dest = tmp_path / "dest"
    run_strip(source, dest)
    first = (dest / "index.html").read_bytes()
    (dest / "assets" / "stale.png").write_bytes(b"x")
    outside = dest / "keep.txt"
    outside.write_text("mine", encoding="utf-8")
    run_strip(source, dest)
    assert (dest / "index.html").read_bytes() == first
    assert not (dest / "assets" / "stale.png").exists()
    assert outside.read_text(encoding="utf-8") == "mine"


def test_traversal_fails_fast_and_writes_nothing(tmp_path):
    src_dir = tmp_path / "src"
    (src_dir / "saved_page_files").mkdir(parents=True)
    (tmp_path / "secret.png").write_bytes(b"secret")
    page = src_dir / "saved_page.html"
    page.write_text('<img src="saved_page_files/../../secret.png" alt="x">', encoding="utf-8")
    dest = tmp_path / "dest"
    with pytest.raises(StripError, match="escapes"):
        run_strip(page, dest)
    assert not dest.exists()


def test_symlink_escape_fails_fast(tmp_path):
    src_dir = tmp_path / "src"
    (src_dir / "saved_page_files").mkdir(parents=True)
    (tmp_path / "secret.png").write_bytes(b"secret")
    (src_dir / "saved_page_files" / "link.png").symlink_to(tmp_path / "secret.png")
    page = src_dir / "saved_page.html"
    page.write_text('<img src="saved_page_files/link.png" alt="x">', encoding="utf-8")
    with pytest.raises(StripError, match="escapes"):
        run_strip(page, tmp_path / "dest")
    assert not (tmp_path / "dest").exists()


def test_missing_local_file_fails_fast(tmp_path):
    (tmp_path / "saved_page_files").mkdir()
    page = tmp_path / "saved_page.html"
    page.write_text('<img src="saved_page_files/nope.png" alt="x">', encoding="utf-8")
    with pytest.raises(StripError, match="missing"):
        run_strip(page, tmp_path / "dest")


def test_srcset_candidates_handled_individually(tmp_path):
    files = tmp_path / "p_files"
    files.mkdir()
    (files / "a.png").write_bytes(b"a")
    (files / "b.png").write_bytes(b"b")
    page = tmp_path / "p.html"
    page.write_text(
        '<img alt="x" srcset="p_files/a.png 1x, https://cdn.example.com/c.png 2x, p_files/b.png 3x">'
        '<picture><source srcset="https://cdn.example.com/d.webp"></picture>',
        encoding="utf-8",
    )
    report = run_strip(page, tmp_path / "d")
    out = (tmp_path / "d" / "index.html").read_text(encoding="utf-8")
    assert 'srcset="assets/a.png 1x, assets/b.png 3x"' in out
    assert "<source>" in out
    assert report.removed_remote == ["https://cdn.example.com/c.png", "https://cdn.example.com/d.webp"]
    assert validate_page(tmp_path / "d" / "index.html") == []


def test_cli_success_prints_report(source, tmp_path):
    dest = tmp_path / "dest"
    result = run_cli("strip_page.py", source, dest)
    assert result.returncode == 0, result.stderr
    assert "localized assets: 1" in result.stdout
    assert "https://ads.example.com/frame" in result.stdout
    assert "words:" in result.stdout
    assert (dest / "index.html").is_file()


@pytest.mark.parametrize("args", [[], ["only-one.html"], ["a", "b", "c"]])
def test_cli_usage_errors_exit_2(args):
    result = run_cli("strip_page.py", *args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


def test_cli_traversal_exits_1_with_one_line(tmp_path):
    (tmp_path / "saved_page_files").mkdir()
    page = tmp_path / "saved_page.html"
    page.write_text('<img src="saved_page_files/../x.png" alt="x">', encoding="utf-8")
    result = run_cli("strip_page.py", page, tmp_path / "dest")
    assert result.returncode == 1
    assert result.stderr.startswith("error:")
    assert not (tmp_path / "dest").exists()


# ---- outline -----------------------------------------------------------


def test_outline_of_fixture_is_short_and_safe(stripped):
    _, dest, _ = stripped
    text = outline_page.outline(dest / "index.html")
    assert 0 < len(text.splitlines()) < 400
    assert "<script" not in text
    assert "* header data-el=El1" in text
    assert "* main data-el=El2" in text
    assert re.search(r'^\s+li ".*" ×3$', text, re.M)
    assert "<" not in text and "=" not in text.replace("data-el=", "").replace("data-sp=", "")


def test_outline_group_marks_repeats_and_caps_lines(tmp_path):
    rows = "".join("<tr><td>Name %d</td><td>x</td></tr>" % i for i in range(2000))
    page = tmp_path / "big.html"
    page.write_text("<table>%s</table>" % rows, encoding="utf-8")
    text = outline_page.outline(page)
    assert "tr ×2000" in text
    assert len(text.splitlines()) < 400


def test_outline_truncates_with_omitted_count(tmp_path):
    items = "".join("<p>para %d</p><div>%d</div>" % (i, i) for i in range(600))
    page = tmp_path / "many.html"
    page.write_text("<body>%s</body>" % items, encoding="utf-8")
    lines = outline_page.outline(page).splitlines()
    assert len(lines) == 400
    assert re.fullmatch(r"\.\.\. \d+ more lines omitted", lines[-1])


def test_outline_never_leaks_raw_attributes_or_markup(tmp_path):
    page = tmp_path / "evil.html"
    page.write_text(
        '<div id="a&quot;&gt;&lt;script&gt;x" data-el="E&lt;script&gt;" href="http://x" class="c" '
        'onclick="steal()">&lt;script&gt;alert(1)&lt;/script&gt; hello</div><script>var x</script>',
        encoding="utf-8",
    )
    text = outline_page.outline(page)
    assert "<" not in text and ">" not in text
    assert "steal" not in text and "http" not in text and 'class' not in text


def test_outline_snippets_are_short(tmp_path):
    page = tmp_path / "long.html"
    page.write_text("<p>%s</p>" % ("word " * 50), encoding="utf-8")
    line = outline_page.outline(page)
    assert len(line.split('"')[1]) < 60


def test_outline_max_depth_marks_hidden_children(tmp_path):
    page = tmp_path / "deep.html"
    page.write_text("<div><div><div><span>deep</span></div></div></div>", encoding="utf-8")
    text = outline_page.outline(page, max_depth=2)
    assert text.splitlines() == ["div", "  div …"]


def test_outline_cli(stripped):
    _, dest, _ = stripped
    result = run_cli("outline_page.py", dest / "index.html", "--max-depth", "3")
    assert result.returncode == 0, result.stderr
    assert "* main" in result.stdout


@pytest.mark.parametrize("args", [[], ["a.html", "b.html"], ["a.html", "--max-depth"], ["a.html", "--max-depth", "x"]])
def test_outline_cli_usage_errors_exit_2(args):
    result = run_cli("outline_page.py", *args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


# ---- fix round 1: hostile input ------------------------------------------


def _page(tmp_path, body, name="p.html"):
    page = tmp_path / name
    page.write_text(body, encoding="utf-8")
    return page


def _out(dest):
    return (dest / "index.html").read_text(encoding="utf-8")


def _squash(text):
    return re.sub(r"[\x00-\x20\x7f]", "", text).lower()


def _prepared_dest(tmp_path):
    dest = tmp_path / "dest"
    (dest / "assets").mkdir(parents=True)
    (dest / "assets" / "old.png").write_bytes(b"old")
    (dest / "index.html").write_text("old", encoding="utf-8")
    return dest


def _assert_untouched(dest):
    assert (dest / "index.html").read_text(encoding="utf-8") == "old"
    assert [p.name for p in (dest / "assets").iterdir()] == ["old.png"]
    assert sorted(p.name for p in dest.iterdir()) == ["assets", "index.html"]


DROPPED_WITH_DATA_EL = [
    ("<img data-el=E1 src=//evil/x.png>", "E1", "img"),
    ('<img data-el=E1 width=1 height=1 src="https://t.example/p.gif">', "E1", "img"),
    ('<img data-el=E1 width="1" height="1" alt="x">', "E1", "img"),
    ("<iframe data-el=E2 src=https://x></iframe>", "E2", "iframe"),
    ('<script data-el=E3>x</script>', "E3", "script"),
    ('<noscript><p data-el=E4>x</p></noscript>', "E4", "p"),
    ('<svg><set data-el=E5 attributename=x></set></svg>', "E5", "set"),
    ('<img data-el=E6 src="data:text/html,x">', "E6", "img"),
]


@pytest.mark.parametrize("body,el_id,tag", DROPPED_WITH_DATA_EL)
def test_dropped_element_with_data_el_fails_fast(tmp_path, body, el_id, tag):
    page = _page(tmp_path, "<p>hello world</p>" + body)
    dest = _prepared_dest(tmp_path)
    with pytest.raises(StripError) as info:
        run_strip(page, dest)
    assert el_id in str(info.value) and tag in str(info.value)
    _assert_untouched(dest)


def test_cli_dropped_data_el_exits_1_with_one_line(tmp_path):
    page = _page(tmp_path, "<img data-el=E1 src=//evil/x.png>")
    result = run_cli("strip_page.py", page, tmp_path / "dest")
    assert result.returncode == 1
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1 and "E1" in result.stderr
    assert not (tmp_path / "dest").exists()


HOSTILE_URLS = [
    '<a href="java\tscript:alert(1)">x</a>',
    '<a href="java&#10;script:alert(1)">x</a>',
    '<a href="  JaVaScRiPt:x">x</a>',
    '<a href="\x01\x02javascript:x">x</a>',
    '<a href="vbscript:x">x</a>',
    '<a href="data:text/html,<b>x</b>">x</a>',
    "<form action=javascript:x><button formaction=javascript:y>go</button></form>",
    "<svg><set attributename=href to=javascript:x></set></svg>",
    "<svg><a xlink:href=javascript:x>t</a></svg>",
    "<svg><a href=' java\nscript:x'>t</a></svg>",
    "<svg><use href=javascript:x></use></svg>",
    "<svg><animate attributename=href values=javascript:x></animate></svg>",
    "<svg><circle to=javascript:x values=javascript:y from=javascript:z by=javascript:w></circle></svg>",
    "<svg><foreignObject><a href=javascript:x>t</a></foreignObject></svg>",
    "<math><mi href=javascript:x>t</mi></math>",
    "<video poster=javascript:x></video>",
    '<img alt="x" src="java\tscript:x">',
    '<img alt="x" srcset="javascript:x 1x">',
    '<img alt="x" src="data:text/html,x">',
]


@pytest.mark.parametrize("body", HOSTILE_URLS)
def test_hostile_urls_never_reach_output(tmp_path, body):
    page = _page(tmp_path, "<p>keep me</p>" + body)
    run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    assert "javascript" not in _squash(out)
    assert "vbscript" not in _squash(out) and "data:text" not in _squash(out)
    assert validate_page(tmp_path / "d" / "index.html") == []


def test_svg_animation_elements_and_value_attributes_removed(tmp_path):
    page = _page(
        tmp_path,
        "<svg><g to=a values=b from=c by=d><set/><animate/><animateTransform/><animateMotion/>"
        "<foreignObject><p>inner</p></foreignObject><rect width=1 /></g></svg>",
    )
    run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    for gone in ("<set", "<animate", "foreignobject", "inner", " to=", " values=", " from=", " by="):
        assert gone not in out.lower()
    assert "<rect" in out


def test_safe_urls_survive(tmp_path):
    page = _page(
        tmp_path,
        '<a href="#frag">a</a><a href="/path">b</a><a href="rel/x.html">c</a>'
        '<a href="mailto:a@b.co">d</a><a href="tel:+15551234">e</a>'
        '<a href="https://example.com/x">f</a>'
        '<svg><a href="https://example.com/y">g</a><a xlink:href="#frag">h</a></svg>'
        '<form action="/submit"></form><img alt="x" src="data:image/png;base64,AAAA">',
    )
    report = run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    for kept in (
        'href="#frag"', 'href="/path"', 'href="rel/x.html"', 'href="mailto:a@b.co"',
        'href="tel:+15551234"', 'href="https://example.com/x"', 'href="https://example.com/y"',
        'xlink:href="#frag"', 'action="/submit"', 'src="data:image/png;base64,AAAA"',
    ):
        assert kept in out
    assert report.removed_unsafe == []


def test_removed_unsafe_lists_normalized_values(tmp_path):
    page = _page(tmp_path, '<a href="java\tscript:alert(1)">x</a><a href="vbscript:y">z</a>')
    report = run_strip(page, tmp_path / "d")
    assert report.removed_unsafe == ["javascript:alert(1)", "vbscript:y"]
    assert report.removed_remote == []
    result = run_cli("strip_page.py", page, tmp_path / "d2")
    assert "removed unsafe urls: 2" in result.stdout and "  vbscript:y" in result.stdout


# ---- fix round 1: usage errors -------------------------------------------


def _one_line_usage_error(result):
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


def test_cli_strip_source_not_a_file(tmp_path):
    _one_line_usage_error(run_cli("strip_page.py", tmp_path, tmp_path / "d"))


def test_cli_strip_source_missing(tmp_path):
    _one_line_usage_error(run_cli("strip_page.py", tmp_path / "nope.html", tmp_path / "d"))


def test_cli_strip_dest_is_a_file(tmp_path):
    page = _page(tmp_path, "<p>x</p>")
    dest = _page(tmp_path, "i am a file", "dest")
    _one_line_usage_error(run_cli("strip_page.py", page, dest))
    assert dest.read_text(encoding="utf-8") == "i am a file"


def test_strip_dest_is_a_file_raises(tmp_path):
    page = _page(tmp_path, "<p>x</p>")
    dest = _page(tmp_path, "file", "dest")
    with pytest.raises(StripError, match="not a directory"):
        run_strip(page, dest)


@pytest.mark.parametrize("target", ["dir", "missing"])
def test_cli_outline_not_a_file(tmp_path, target):
    arg = tmp_path if target == "dir" else tmp_path / "nope.html"
    _one_line_usage_error(run_cli("outline_page.py", arg))


# ---- fix round 1: minor items --------------------------------------------


def test_asset_names_unique_case_insensitively(tmp_path):
    (tmp_path / "p_files" / "a").mkdir(parents=True)
    (tmp_path / "p_files" / "b").mkdir()
    (tmp_path / "p_files" / "a" / "I.png").write_bytes(b"upper")
    (tmp_path / "p_files" / "b" / "i.png").write_bytes(b"lower")
    page = _page(tmp_path, '<img alt="x" src="p_files/a/I.png"><img alt="x" src="p_files/b/i.png">')
    report = run_strip(page, tmp_path / "d")
    assert report.localized == ["assets/I.png", "assets/i-2.png"]
    assert len({n.casefold() for n in report.localized}) == 2
    assert (tmp_path / "d" / "assets" / "I.png").read_bytes() == b"upper"
    assert (tmp_path / "d" / "assets" / "i-2.png").read_bytes() == b"lower"


def test_basename_collision_from_two_subdirectories(tmp_path):
    for sub, data in (("a", b"A"), ("b", b"B")):
        (tmp_path / "p_files" / sub).mkdir(parents=True)
        (tmp_path / "p_files" / sub / "logo.png").write_bytes(data)
    page = _page(tmp_path, '<img alt="x" src="p_files/a/logo.png"><img alt="x" src="p_files/b/logo.png">')
    run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    assert 'src="assets/logo.png"' in out and 'src="assets/logo-2.png"' in out
    assert (tmp_path / "d" / "assets" / "logo.png").read_bytes() == b"A"
    assert (tmp_path / "d" / "assets" / "logo-2.png").read_bytes() == b"B"


def test_symlinked_files_directory_rejected(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "a.png").write_bytes(b"a")
    (tmp_path / "p_files").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    page = _page(tmp_path, '<img alt="x" src="p_files/a.png">')
    with pytest.raises(StripError, match="symlink"):
        run_strip(page, tmp_path / "d")
    assert not (tmp_path / "d").exists()


def test_unknown_and_known_entities_round_trip(tmp_path):
    page = _page(tmp_path, "<p>a &foo; b &notit; c &amp; d&nbsp;e &copy; f &#65;</p>")
    run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    assert "a &amp;foo; b &amp;notit; c &amp; d&nbsp;e \u00a9 f A" in out


def test_html_tree_has_no_close_override():
    import html_tree

    assert "close" not in html_tree._Builder.__dict__


def test_outline_title_ignores_noscript_and_template(tmp_path):
    page = _page(
        tmp_path,
        "<head><noscript><title>Evil</title></noscript><template><title>Tpl</title></template>"
        "<title>Real</title></head><body><p>x</p></body>",
    )
    text = outline_page.outline(page)
    assert 'title "Real"' in text
    assert "Evil" not in text and "Tpl" not in text


def test_failed_asset_copy_keeps_previous_assets(source, tmp_path):
    dest = tmp_path / "dest"
    run_strip(source, dest)
    before = (dest / "index.html").read_bytes()
    (dest / "assets" / "marker.txt").write_text("previous", encoding="utf-8")
    unreadable = source.parent / "saved_page_files" / "logo.png"
    unreadable.chmod(0)
    try:
        with pytest.raises(StripError, match="logo.png"):
            run_strip(source, dest)
    finally:
        unreadable.chmod(0o644)
    assert (dest / "assets" / "marker.txt").read_text(encoding="utf-8") == "previous"
    assert (dest / "index.html").read_bytes() == before
    assert sorted(p.name for p in dest.iterdir()) == ["assets", "index.html"]


# ---- fix round 1: pinned behavior ----------------------------------------


def test_uppercase_tags_attrs_and_unquoted_values(tmp_path):
    (tmp_path / "p_files").mkdir()
    (tmp_path / "p_files" / "a.png").write_bytes(b"a")
    page = _page(
        tmp_path,
        "<HTML LANG=en><BODY><DIV DATA-EL=A ID=top CLASS=x STYLE='color:red'>"
        "<IMG SRC=p_files/a.png ALT=pic ONERROR=boom()><A HREF=#top ONCLICK=x>up</A>"
        "<SCRIPT>bad()</SCRIPT><IFRAME SRC=https://ads.example/f></IFRAME><P>Hello there</DIV>",
    )
    report = run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    assert validate_page(tmp_path / "d" / "index.html", set(report.source_el_ids)) == []
    assert report.source_el_ids == ["A"]
    assert 'data-el="A"' in out and 'src="assets/a.png"' in out and 'href="#top"' in out
    assert "<IMG" not in out and "SCRIPT" not in out.upper().replace("<LINK", "")
    assert "iframe" not in out.lower() and "boom" not in out


@pytest.mark.parametrize(
    "ref",
    ["other_dir/x.png", "../x.png", "file:///etc/passwd", "FILE:///etc/passwd"],
)
def test_references_outside_files_dir_are_dropped_and_listed(tmp_path, ref):
    page = _page(tmp_path, '<p>t</p><img alt="x" src="%s"><video poster="%s"></video>' % (ref, ref))
    report = run_strip(page, tmp_path / "d")
    out = _out(tmp_path / "d")
    assert report.removed_remote == [ref]
    assert report.removed_unsafe == []
    assert "x.png" not in out and "passwd" not in out and "poster" not in out


def _browser_saved_page(tmp_path, body):
    page = tmp_path / "My Page's _ Test.html"
    files = tmp_path / "My Page's _ Test_files"
    files.mkdir()
    for name in ("a.png", "vt", "vt(1)"):
        (files / name).write_bytes(name.encode())
    page.write_text(body, encoding="utf-8")
    return page


def test_dot_slash_references_into_files_dir_are_localized(tmp_path):
    d = "My Page's _ Test_files"
    page = _browser_saved_page(
        tmp_path,
        '<img src="./%s/a.png" alt="a"><img src="./%s/vt" alt="b">'
        '<img src="./%s/vt(1)" alt="c">' % (d, d, d),
    )
    dest = tmp_path / "dest"
    report = run_strip(page, dest)
    assert sorted(report.localized) == ["assets/a.png", "assets/vt", "assets/vt_1_"]
    assert report.removed_remote == []
    for name in report.localized:
        assert (dest / name).is_file()


def test_percent_encoded_references_are_localized(tmp_path):
    page = _browser_saved_page(
        tmp_path,
        '<img src="./My%20Page%27s%20_%20Test_files/a.png" alt="a">'
        '<img src="My%20Page\'s%20_%20Test_files/vt%281%29" alt="b">',
    )
    dest = tmp_path / "dest"
    report = run_strip(page, dest)
    assert len(report.localized) == 2 and report.removed_remote == []
    assert all((dest / n).is_file() for n in report.localized)


def test_dot_slash_srcset_candidates_are_localized(tmp_path):
    page = _browser_saved_page(
        tmp_path,
        '<img srcset="./My%20Page%27s%20_%20Test_files/a.png 1x, '
        './My%20Page%27s%20_%20Test_files/vt 2x" alt="a">',
    )
    report = run_strip(page, tmp_path / "dest")
    assert sorted(report.localized) == ["assets/a.png", "assets/vt"]
    assert report.removed_remote == []


def test_dot_slash_escapes_still_rejected(tmp_path):
    page = tmp_path / "x.html"
    (tmp_path / "x_files").mkdir()
    (tmp_path / "secret.png").write_bytes(b"s")
    page.write_text('<img src="./x_files/../../secret.png" alt="a">', encoding="utf-8")
    with pytest.raises(StripError, match="escapes"):
        run_strip(page, tmp_path / "d1")
    page.write_text('<img src="./../outside.png" alt="a">', encoding="utf-8")
    report = run_strip(page, tmp_path / "d2")
    assert report.localized == [] and "./../outside.png" in report.removed_remote
    assert not (tmp_path / "d1").exists()


def _strip_body(tmp_path, body):
    src = tmp_path / "svgsrc"
    src.mkdir()
    page = src / "p.html"
    page.write_text("<html><head><title>t</title></head><body>%s</body></html>" % body, encoding="utf-8")
    report = run_strip(page, tmp_path / "svgdest")
    return report, (tmp_path / "svgdest" / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("attr", ["fill", "filter", "mask", "clip-path", "cursor", "marker-start", "marker-mid", "marker-end"])
@pytest.mark.parametrize(
    "url", ["https://evil.example/x.svg#a", "//evil.example/x.svg", "data:image/svg+xml,%3Csvg/%3E", "HTTP://evil.example/x"]
)
def test_svg_remote_url_attributes_dropped(tmp_path, attr, url):
    report, out = _strip_body(tmp_path, '<svg><rect %s="url(%s)" width="3"></rect></svg>' % (attr, url))
    assert "evil" not in out and "data:" not in out and attr + "=" not in out
    assert 'width="3"' in out
    assert report.removed_remote or report.removed_unsafe


def test_quoted_and_spaced_url_dropped(tmp_path):
    _, out = _strip_body(tmp_path, '<svg><rect fill="URL( &quot; https://evil.example/a &quot; )"></rect></svg>')
    assert "evil" not in out


def test_fragment_url_kept(tmp_path):
    report, out = _strip_body(
        tmp_path, "<svg><defs><linearGradient id=\"grad\"></linearGradient></defs><rect fill=\"url(#grad)\" stroke=\"url('#grad') none\"></rect></svg>"
    )
    assert 'fill="url(#grad)"' in out
    assert "url('#grad')" in out.replace("&#x27;", "'")
    assert not report.removed_remote


def test_mixed_fragment_and_remote_dropped(tmp_path):
    _, out = _strip_body(tmp_path, '<svg><rect filter="url(#a) url(https://evil.example/f)"></rect></svg>')
    assert "filter=" not in out


def test_url_in_non_svg_attribute_dropped(tmp_path):
    report, out = _strip_body(tmp_path, '<div title="url(https://evil.example/t)">x</div>')
    assert "evil" not in out
    assert report.removed_remote == ["https://evil.example/t"]


def test_javascript_url_listed_as_unsafe(tmp_path):
    report, out = _strip_body(tmp_path, '<svg><rect fill="url(javascript:alert(1))"></rect></svg>')
    assert "javascript" not in out and report.removed_unsafe


def test_css_escaped_url_dropped(tmp_path):
    _, out = _strip_body(tmp_path, '<svg><rect fill="u\\72l(https://evil.example/x)" mask="\\75rl(//evil.example)"></rect></svg>')
    assert "evil" not in out and "fill=" not in out and "mask=" not in out


def test_xml_base_dropped_everywhere(tmp_path):
    _, out = _strip_body(tmp_path, '<svg xml:base="https://evil.example/"><use></use></svg><p xml:base="//evil.example/">x</p>')
    assert "xml:base" not in out and "evil" not in out
