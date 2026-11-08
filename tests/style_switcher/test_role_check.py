from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from role_check import coverage
from strip_page import strip_page
from validate_page import collect_data_el, validate_page

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "style-switcher" / "scripts" / "role_check.py"

PAGE = """<!DOCTYPE html>
<html><head><title>t</title></head>
<body>
<div data-sp="shell"><header data-sp="header"><h1>Hi</h1></header>
<main data-sp="content"><p>text</p><p>more</p></main></div>
</body></html>
"""


def write(tmp_path, text, name="page.html"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT)] + [str(a) for a in args],
        capture_output=True,
        text=True,
    )


def test_counts_on_small_page(tmp_path):
    assert coverage(write(tmp_path, PAGE)) == {
        "roled_elements": 3,
        "total_elements": 6,
        "has_shell": True,
        "has_content": True,
    }


def test_head_elements_are_not_counted(tmp_path):
    page = '<html><head><title>t</title><meta charset="utf-8"></head><body><p>x</p></body></html>'
    result = coverage(write(tmp_path, page))
    assert result["total_elements"] == 1


def test_no_roles(tmp_path):
    result = coverage(write(tmp_path, "<body><p>x</p></body>"))
    assert result == {
        "roled_elements": 0,
        "total_elements": 1,
        "has_shell": False,
        "has_content": False,
    }


def test_shell_without_content(tmp_path):
    result = coverage(write(tmp_path, '<body><div data-sp="shell"><p>x</p></div></body>'))
    assert result["has_shell"] is True
    assert result["has_content"] is False


def test_content_without_shell(tmp_path):
    result = coverage(write(tmp_path, '<body><div data-sp="content"><p>x</p></div></body>'))
    assert result["has_shell"] is False
    assert result["has_content"] is True


def test_missing_file_fails_fast(tmp_path):
    with pytest.raises(FileNotFoundError):
        coverage(tmp_path / "nope.html")


def test_cli_prints_sorted_json_and_exits_0(tmp_path):
    result = run_cli(write(tmp_path, PAGE))
    assert result.returncode == 0
    assert result.stderr == ""
    assert list(json.loads(result.stdout)) == [
        "has_content",
        "has_shell",
        "roled_elements",
        "total_elements",
    ]
    assert json.loads(result.stdout)["roled_elements"] == 3


def test_cli_exit_1_when_shell_missing(tmp_path):
    result = run_cli(write(tmp_path, "<body><p>x</p></body>"))
    assert result.returncode == 1
    assert result.stderr == "has_shell missing\n"
    assert json.loads(result.stdout)["has_shell"] is False


@pytest.mark.parametrize("args", [[], ["a.html", "b.html"]])
def test_cli_usage_error(args):
    result = run_cli(*args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert result.stderr.startswith("usage:")


def test_cli_missing_file_is_one_line_exit_2(tmp_path):
    result = run_cli(tmp_path / "nope.html")
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


def test_tiny_page_strips_cleanly_and_validates(tmp_path):
    src = FIXTURES / "tiny_page.html"
    assert collect_data_el(src) == {"El1"}
    dest = tmp_path / "dest"
    report = strip_page(src, dest)
    assert report.source_el_ids == ["El1"]
    stripped = dest / "index.html"
    text = stripped.read_text(encoding="utf-8")
    for forbidden in ("<script", "<style", "onclick", 'class="'):
        assert forbidden not in text
    assert validate_page(stripped, source_el_ids={"El1"}) == []
    assert report.words_after / report.words_before >= 0.9


def test_tiny_page_is_a_realistic_saved_page():
    text = (FIXTURES / "tiny_page.html").read_text(encoding="utf-8")
    assert 25 <= len(text.splitlines()) <= 40
    assert text.count("<li class=\"card\"") == 3
    assert text.count("data-el=") == 1
    assert "onclick=" in text


def test_mockup_attribute_counts_are_pinned():
    text = (FIXTURES / "mockup.html").read_text(encoding="utf-8")
    assert len(re.findall(r"\sdata-el=", text)) == 6
    assert len(re.findall(r"\sdata-action=", text)) == 9
    assert len(re.findall(r"\sdata-exit=", text)) == 8
    assert collect_data_el(FIXTURES / "mockup.html") == {"El1", "El2", "El3", "El4", "El5", "El6"}


def test_mockup_meets_contract_except_slots_and_roles():
    problems = validate_page(FIXTURES / "mockup.html", source_el_ids={"El1", "El2", "El3", "El4", "El5", "El6"})
    assert sorted(p.code for p in problems) == ["missing-slot", "missing-slot"]
    text = (FIXTURES / "mockup.html").read_text(encoding="utf-8")
    assert "data-sp" not in text
    assert coverage(FIXTURES / "mockup.html")["roled_elements"] == 0
