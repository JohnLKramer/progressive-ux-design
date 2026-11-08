from __future__ import annotations

import pytest

from validate_page import collect_data_el, validate_page

SLOTS = (
    '<link id="sp-style" rel="stylesheet">'
    '<link id="sp-layout" rel="stylesheet">'
)


def page(body="", head_extra="", slots=SLOTS):
    return "<html><head>%s%s</head><body>%s</body></html>" % (slots, head_extra, body)


def write(tmp_path, html):
    p = tmp_path / "page.html"
    p.write_text(html)
    return p


def codes(tmp_path, html, **kwargs):
    return [p.code for p in validate_page(write(tmp_path, html), **kwargs)]


def test_clean_page(tmp_path):
    assert validate_page(write(tmp_path, page('<div data-sp="card" data-sp-variant="primary"></div>'))) == []


@pytest.mark.parametrize(
    "html,code",
    [
        (page("<script>1</script>"), "script"),
        (page(head_extra="<style>a{}</style>"), "style-tag"),
        (page('<p style="color:red">x</p>'), "inline-style"),
        (page('<button onclick="go()">x</button>'), "event-handler"),
        (page('<img src="https://x/y.png">'), "remote-asset"),
        (page(head_extra='<link rel=stylesheet href=http://x/y.css>'), "remote-asset"),
        (page('<img src="//x/y.png">'), "remote-asset"),
        (page('<video poster="https://x/p.png"></video>'), "remote-asset"),
        (page('<img srcset="https://x/a.png 1x">'), "remote-asset"),
        (page('<div data-sp="banner"></div>'), "bad-role"),
    ],
)
def test_problem_codes(tmp_path, html, code):
    assert code in codes(tmp_path, html)


def test_srcset_second_candidate_remote(tmp_path):
    html = page('<img srcset="a.png 1x, https://x/b.png 2x">')
    assert codes(tmp_path, html) == ["remote-asset"]


def test_srcset_all_local_is_clean(tmp_path):
    assert codes(tmp_path, page('<img srcset="a.png 1x, b.png 2x">')) == []


def test_srcset_data_uri_is_not_mis_split(tmp_path):
    # base64 payload after the comma starts with "//", which must not read as remote
    html = page('<img srcset="data:image/png;base64,//8AAA 1x, b.png 2x">')
    assert codes(tmp_path, html) == []


def test_srcset_remote_after_data_uri(tmp_path):
    html = page('<img srcset="data:image/png;base64,//8AAA 1x, https://x/b.png 2x">')
    assert codes(tmp_path, html) == ["remote-asset"]


def test_bare_data_sp_is_bad_role(tmp_path):
    assert codes(tmp_path, page("<div data-sp></div>")) == ["bad-role"]


def test_empty_data_sp_is_bad_role(tmp_path):
    assert codes(tmp_path, page('<div data-sp=""></div>')) == ["bad-role"]


def test_anchor_href_is_not_asset(tmp_path):
    assert codes(tmp_path, page('<a href="https://x.com">x</a>')) == []


def test_slot_links_without_href_are_not_remote(tmp_path):
    assert "remote-asset" not in codes(tmp_path, page())


def test_lost_data_el_names_missing_id(tmp_path):
    html = page('<div data-el="El1"></div>')
    problems = validate_page(write(tmp_path, html), source_el_ids={"El1", "El2"})
    assert [p.code for p in problems] == ["lost-data-el"]
    assert "El2" in problems[0].message + problems[0].where


@pytest.mark.parametrize(
    "slots",
    ['<link id="sp-layout" rel="stylesheet">', '<link id="sp-style" rel="stylesheet">'],
)
def test_missing_slot(tmp_path, slots):
    assert codes(tmp_path, page(slots=slots)) == ["missing-slot"]


def test_fragment_without_head_is_missing_slot(tmp_path):
    assert "missing-slot" in codes(tmp_path, "<div>x</div>")


def test_collect_data_el(tmp_path):
    p = write(tmp_path, page('<div data-el="A"><p data-el="B"></p></div>'))
    assert collect_data_el(p) == {"A", "B"}


def test_unreadable_file_raises(tmp_path):
    with pytest.raises(OSError):
        validate_page(tmp_path / "nope.html")


@pytest.mark.parametrize(
    "value",
    ["url(https://x/y.svg)", "url(//x/y)", "URL( 'data:image/png;base64,AA' )", 'url("http://x")', "url(foo.png)"],
)
def test_remote_url_in_attribute_value_flagged(tmp_path, value):
    html = page('<svg><rect fill="%s"></rect></svg>' % value.replace('"', "&quot;"))
    assert "remote-asset" in codes(tmp_path, html)


def test_fragment_url_in_attribute_value_not_flagged(tmp_path):
    for value in ("url(#grad)", "url( '#grad' )", 'url(&quot;#g&quot;) none'):
        assert codes(tmp_path, page('<svg><rect fill="%s"></rect></svg>' % value)) == []


def test_duplicate_attribute_is_reported(tmp_path):
    html = page('<a data-sp="link" data-sp="button" href="/x">x</a>')
    problems = validate_page(write(tmp_path, html))
    assert [p.code for p in problems] == ["duplicate-attr"]
    assert "data-sp" in problems[0].message


def test_duplicate_attribute_is_case_insensitive_and_any_name(tmp_path):
    assert "duplicate-attr" in codes(tmp_path, page('<p id="a" ID="b">x</p>'))


def test_hidden_attribute_is_allowed(tmp_path):
    assert validate_page(write(tmp_path, page('<div hidden data-sp="card">x</div>'))) == []
