import pytest

import gates


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("<html><body>%s</body></html>" % body, encoding="utf-8")
    return p


def test_identical_markers_pass(tmp_path):
    body = '<div data-el="a"><button data-action="go">x</button></div>'
    a = _write(tmp_path, "a.html", body)
    b = _write(tmp_path, "b.html", body)
    assert gates.marker_diff(a, b) == []


def test_reordered_and_wrapped_elements_pass(tmp_path):
    a = _write(tmp_path, "a.html", '<p data-el="a"></p><p data-el="b" data-variant="v1"></p>')
    b = _write(
        tmp_path,
        "b.html",
        '<div class="wrap"><p data-el="b" data-variant="v1"></p></div><section><p data-el="a"></p></section>',
    )
    assert gates.marker_diff(a, b) == []


def test_lost_data_el_reports_marker_lost(tmp_path):
    a = _write(tmp_path, "a.html", '<p data-el="a"></p><p data-el="b"></p>')
    b = _write(tmp_path, "b.html", '<p data-el="a"></p>')
    problems = gates.marker_diff(a, b)
    assert [p.code for p in problems] == ["marker-lost"]
    assert "data-el" in problems[0].message and "b" in problems[0].message


def test_added_data_action_reports_marker_added(tmp_path):
    a = _write(tmp_path, "a.html", '<p data-el="a"></p>')
    b = _write(tmp_path, "b.html", '<p data-el="a"></p><button data-action="buy"></button>')
    problems = gates.marker_diff(a, b)
    assert [p.code for p in problems] == ["marker-added"]
    assert "data-action" in problems[0].message and "buy" in problems[0].message


def test_duplicate_variant_count_change_is_reported(tmp_path):
    a = _write(tmp_path, "a.html", '<i data-variant="x"></i><i data-variant="x"></i>')
    b = _write(tmp_path, "b.html", '<i data-variant="x"></i>')
    problems = gates.marker_diff(a, b)
    assert [p.code for p in problems] == ["marker-lost"]


def test_missing_file_raises(tmp_path):
    a = _write(tmp_path, "a.html", "")
    with pytest.raises(OSError):
        gates.marker_diff(a, tmp_path / "nope.html")
