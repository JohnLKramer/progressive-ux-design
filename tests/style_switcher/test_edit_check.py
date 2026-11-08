from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from edit_check import check_edits
from strip_page import strip_page

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALIDATE = Path(__file__).resolve().parents[2] / "skills" / "style-switcher" / "scripts" / "validate.py"


def stripped_text(fixture: str, tmp_path: Path) -> str:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    shutil.copy(FIXTURES / fixture, src / fixture)
    dest = tmp_path / "stripped"
    strip_page(src / fixture, dest)
    return (dest / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def tiny(tmp_path):
    source = tmp_path / "src" / "tiny_page.html"
    text = stripped_text("tiny_page.html", tmp_path)
    return source, text, tmp_path


def final_of(tmp_path, text):
    path = tmp_path / "final.html"
    path.write_text(text, encoding="utf-8")
    return path


def annotate(text):
    text = text.replace("<header>", '<header data-sp="header">')
    text = text.replace("<nav>", '<nav data-sp="nav">')
    text = text.replace("<main>", '<div data-sp="shell"><main data-sp="content">').replace("</main>", "</main></div>")
    text = text.replace('<li data-el="El1">', '<li data-el="El1" data-sp="card" data-sp-variant="primary">')
    return text.replace("<button>Reserve", '<button data-sp="button">Reserve')


def codes(problems):
    return [p.code for p in problems]


def test_clean_annotation_passes(tiny):
    source, text, tmp_path = tiny
    assert check_edits(source, final_of(tmp_path, annotate(text))) == []


def test_unannotated_stripped_page_passes(tiny):
    source, text, tmp_path = tiny
    assert check_edits(source, final_of(tmp_path, text)) == []


def test_bare_div_wrapper_passes(tiny):
    source, text, tmp_path = tiny
    wrapped = text.replace("<main>", "<div><main>").replace("</main>", "</main></div>")
    assert check_edits(source, final_of(tmp_path, wrapped)) == []


@pytest.mark.parametrize(
    "old,new,fragment",
    [
        ("Morning Flow", "Evening Flow", "text"),
        ("<h3>Lunch Break Ride</h3>", "", "missing"),
        ("<footer>", '<a href="javascript:x">x</a><footer>', "extra"),
        ('href="/classes/morning-flow"', 'href="/classes/other"', "href"),
        ("<footer>", '<footer class="x">', "class"),
        (' data-el="El1"', "", "data-el"),
    ],
)
def test_changes_fail_with_content_changed(tiny, old, new, fragment):
    source, text, tmp_path = tiny
    assert old in text
    problems = check_edits(source, final_of(tmp_path, annotate(text).replace(old, new)))
    assert problems and set(codes(problems)) <= {"content-changed", "words-lost"}
    assert "content-changed" in codes(problems)
    assert any(fragment in p.message for p in problems if p.code == "content-changed")


def test_reordered_siblings_fail(tiny):
    source, text, tmp_path = tiny
    a = "<h2>This week's classes</h2>"
    b = "<footer><p>Copyright Riverside Studio</p></footer>"
    swapped = text.replace(a, "@@A@@").replace(b, a).replace("@@A@@", b)
    assert "content-changed" in codes(check_edits(source, final_of(tmp_path, swapped)))


def test_path_is_reported(tiny):
    source, text, tmp_path = tiny
    problems = check_edits(source, final_of(tmp_path, text.replace("Copyright", "Copyleft")))
    assert [p.where for p in problems if p.code == "content-changed"] == ["body > footer[1] > p[1]"]


def test_wrapper_with_extra_attribute_fails(tiny):
    source, text, tmp_path = tiny
    wrapped = text.replace("<main>", '<div data-sp="shell" id="w"><main>').replace("</main>", "</main></div>")
    assert "content-changed" in codes(check_edits(source, final_of(tmp_path, wrapped)))


def test_dropped_words_fail(tiny):
    source, text, tmp_path = tiny
    problems = check_edits(source, final_of(tmp_path, text.replace("<p>Copyright Riverside Studio</p>", "")))
    assert "words-lost" in codes(problems)


def test_hidden_added_to_small_part_passes(tiny):
    source, text, tmp_path = tiny
    hidden = text.replace("<footer>", "<footer hidden>")
    assert check_edits(source, final_of(tmp_path, hidden)) == []


def test_hidden_wrapper_div_passes(tiny):
    source, text, tmp_path = tiny
    wrapped = text.replace("<footer>", "<div hidden><footer>").replace("</footer>", "</footer></div>")
    assert check_edits(source, final_of(tmp_path, wrapped)) == []


def test_hidden_added_to_large_part_fails_words_hidden(tiny):
    source, text, tmp_path = tiny
    hidden = text.replace("<ul>", "<ul hidden>")
    problems = check_edits(source, final_of(tmp_path, hidden))
    assert "words-hidden" in codes(problems)
    assert "%" in [p for p in problems if p.code == "words-hidden"][0].message


def test_words_hidden_threshold_is_ninety_percent_of_visible(tiny):
    import edit_check, html_tree

    source, text, tmp_path = tiny
    doc = html_tree.parse(text)
    total = html_tree.count_visible_words(doc.head + [doc.body])
    assert edit_check.MIN_VISIBLE_RATIO == 0.9
    assert edit_check.visible_ratio(total, total - total // 10) >= 0.9
    assert edit_check.visible_ratio(total, total - total // 10 - 1) < 0.9


def test_source_hidden_text_is_not_counted_against_the_page(tmp_path):
    src = tmp_path / "src" / "h.html"
    src.parent.mkdir()
    src.write_text("<html><body><p>one two three four five six seven eight nine ten</p>"
                   "<label hidden>a b c d e f g h</label></body></html>", encoding="utf-8")
    dest = tmp_path / "stripped"
    strip_page(src, dest)
    text = (dest / "index.html").read_text(encoding="utf-8")
    assert "hidden" in text
    assert check_edits(src, final_of(tmp_path, text)) == []


def test_removing_a_hidden_attribute_the_source_had_is_a_change(tmp_path):
    src = tmp_path / "src" / "h.html"
    src.parent.mkdir()
    src.write_text("<html><body><p>one</p><label hidden>a b</label></body></html>", encoding="utf-8")
    dest = tmp_path / "stripped"
    strip_page(src, dest)
    text = (dest / "index.html").read_text(encoding="utf-8").replace(" hidden=\"\"", "")
    assert "content-changed" in codes(check_edits(src, final_of(tmp_path, text)))


def test_whitespace_only_differences_pass(tiny):
    source, text, tmp_path = tiny
    spaced = text.replace("<body>\n", "<body>\n\n\n").replace("<main>", "<main>\n\n   ")
    assert check_edits(source, final_of(tmp_path, spaced)) == []


def test_more_than_twenty_differences_are_summarised(tmp_path):
    src = tmp_path / "src.html"
    items = "".join("<p>item %d</p>" % i for i in range(30))
    src.write_text("<html><head><title>t</title></head><body>%s</body></html>" % items, encoding="utf-8")
    final = final_of(tmp_path, stripped_of(src, tmp_path).replace("item", "other"))
    problems = check_edits(src, final)
    changed = [p for p in problems if p.code == "content-changed"]
    assert len(changed) == 21
    assert changed[-1].where == "..." and changed[-1].message == "10 more"


def stripped_of(src, tmp_path):
    dest = tmp_path / "s2"
    strip_page(src, dest)
    return (dest / "index.html").read_text(encoding="utf-8")


def test_strip_failure_becomes_problem(tmp_path):
    src = tmp_path / "bad.html"
    src.write_bytes(b"\xff\xfe\x00bad")
    problems = check_edits(src, final_of(tmp_path, "<p>x</p>"))
    assert codes(problems) == ["strip-failed"]


def test_annotated_mockup_passes(tmp_path):
    text = stripped_text("mockup.html", tmp_path)
    annotated = text.replace("<header ", '<header data-sp="header" ').replace("<nav>", '<div data-sp="shell"><nav data-sp="nav">')
    annotated = annotated.replace("</nav>", "</nav></div>")
    path = final_of(tmp_path, annotated)
    assert check_edits(tmp_path / "src" / "mockup.html", path) == []


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-I", str(VALIDATE)] + [str(a) for a in args], capture_output=True, text=True
    )


def test_cli_clean_exits_0_and_changed_exits_1(tiny):
    source, text, tmp_path = tiny
    good = run_cli("page", final_of(tmp_path, annotate(text)), "--source-html", source)
    assert (good.returncode, good.stdout) == (0, "")
    bad = run_cli("page", final_of(tmp_path, annotate(text).replace("Morning", "Night")), "--source-html", source)
    assert bad.returncode == 1
    assert "content-changed" in bad.stdout


def test_cli_prints_page_and_edit_problems_together(tiny):
    source, text, tmp_path = tiny
    broken = annotate(text).replace('data-sp="header"', 'data-sp="banner"').replace("Morning", "Night")
    result = run_cli("page", final_of(tmp_path, broken), "--source-html", source)
    assert result.returncode == 1
    assert "bad-role" in result.stdout and "content-changed" in result.stdout


WORDS30 = " ".join("w%d" % i for i in range(30))


def write_source(tmp_path, body):
    src = tmp_path / "src" / "p.html"
    src.parent.mkdir(exist_ok=True)
    src.write_text("<html><head><title>t</title></head><body>%s</body></html>" % body, encoding="utf-8")
    return src


def final_from(src, tmp_path, edit):
    text = stripped_of(src, tmp_path)
    edited = edit(text)
    assert edited != text
    return final_of(tmp_path, edited)


def test_hiding_a_form_with_no_words_fails(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><form><input name=q><input type=password name=p></form>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<form>", "<form hidden>"))
    assert "hidden-interactive" in codes(check_edits(src, final))


def test_hiding_a_single_input_or_button_fails(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><input name=q><button type=submit></button>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<input ", "<input hidden "))
    assert "hidden-interactive" in codes(check_edits(src, final))


def test_hiding_a_wordless_button_passes_as_decoration(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><button type=button aria-label='Keyboard shortcuts'></button>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<button ", "<button hidden "))
    assert check_edits(src, final) == []


def test_hiding_a_copy_with_words_and_a_form_is_left_to_the_word_gate(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><div><form>Search <input name=q></form></div>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<form>", "<form hidden>"))
    assert check_edits(src, final) == []


def test_hiding_an_element_with_data_action_fails(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><span data-action='A1'></span>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<span ", "<span hidden "))
    assert "hidden-interactive" in codes(check_edits(src, final))


def test_hiding_wordless_images_still_passes(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><img src='data:image/gif;base64,R0lGODlhAQABAAAAACw='>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<img ", "<img hidden "))
    assert check_edits(src, final) == []


def test_unhiding_a_source_hidden_div_is_reported(tmp_path):
    body = "<p>%s</p><div hidden>h1 h2 h3 h4 h5 h6 h7 h8</div><a href='#x'>a1 a2 a3 a4 a5 a6 a7 a8</a>" % WORDS30
    src = write_source(tmp_path, body)
    final = final_from(src, tmp_path, lambda t: t.replace("<div hidden=\"\">", "<div>").replace("<a ", "<a hidden "))
    assert "unhidden" in codes(check_edits(src, final))


def test_keeping_a_source_hidden_div_hidden_passes(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><div hidden>h1 h2 h3 h4</div>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace("<p>", "<p data-sp=\"text\">"))
    assert check_edits(src, final) == []


def test_ninety_percent_boundary_end_to_end(tmp_path):
    body = "<p>%s</p><p>x1 x2</p><p>y1 y2 y3</p>" % " ".join("w%d" % i for i in range(15))
    src = write_source(tmp_path, body)
    # title "t" adds one word: 21 visible words in all; hiding 2 leaves 19/21 (90.4%), hiding 3 leaves 18/21 (85.7%)
    two = final_from(src, tmp_path, lambda t: t.replace("<p>x1 x2</p>", "<p hidden>x1 x2</p>"))
    assert check_edits(src, two) == []
    three = final_from(src, tmp_path, lambda t: t.replace("<p>y1 y2 y3</p>", "<p hidden>y1 y2 y3</p>"))
    assert "words-hidden" in codes(check_edits(src, three))


def test_swapping_which_wordless_input_is_hidden_is_reported(tmp_path):
    src = write_source(tmp_path, "<p>%s</p><div hidden><input name=a></div><input name=b>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace('<div hidden="">', "<div>").replace("<input name=\"b\"", "<input hidden name=\"b\""))
    assert "unhidden" in codes(check_edits(src, final))


def test_unmatchable_hidden_structure_is_reported_not_skipped(tmp_path):
    src = write_source(tmp_path, "<div hidden>one</div><section>helloworld</section><p>%s</p>" % WORDS30)
    final = final_from(src, tmp_path, lambda t: t.replace('<div hidden="">one</div>', "<div>one</div>").replace("helloworld", "hello<div>world</div>"))
    assert "unhidden" in codes(check_edits(src, final))
