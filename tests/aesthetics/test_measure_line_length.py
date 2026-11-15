import json
import subprocess
import sys
from pathlib import Path

import pytest

from screenshot import playwright_available

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills" / "progressive-ux-design" / "scripts" / "measure_line_length.py"
)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "measure.html"

needs_browser = pytest.mark.skipif(not playwright_available(), reason="Playwright is not importable")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


@pytest.fixture(scope="module")
def blocks():
    proc = run("--html", str(FIXTURE), "--width", "1280")
    assert proc.returncode == 0, proc.stderr
    return {b["selector"]: b for b in json.loads(proc.stdout)}


@needs_browser
def test_narrow_paragraph_is_too_short(blocks):
    b = blocks["p#narrow"]
    # 200px of 16px Courier is about 20 characters per line.
    assert b["lines"] > 1
    assert 17 <= b["median_chars"] <= 22
    assert b["t3"] == "too-short"


@needs_browser
def test_mid_paragraph_is_in_range(blocks):
    b = blocks["p#mid"]
    # 600px of 16px Courier is about 62 characters per line.
    assert 55 <= b["median_chars"] <= 66
    assert b["t3"] == "ok"


@needs_browser
def test_wide_paragraph_is_too_long(blocks):
    b = blocks["p#wide"]
    # 1100px of 16px Courier is about 114 characters per line.
    assert b["max_chars"] > 90
    assert b["t3"] == "too-long"


@needs_browser
def test_one_line_block_is_exempt(blocks):
    b = blocks["p#label"]
    assert b["lines"] == 1
    assert b["t3"] == "one-line"


@needs_browser
def test_nested_block_is_reported_once_and_hidden_is_skipped(blocks):
    assert "p#inner" in blocks
    assert "blockquote#quote" not in blocks
    assert "p#hidden" not in blocks


@needs_browser
def test_font_size_is_reported(blocks):
    assert blocks["p#mid"]["font_px"] == 16


def test_missing_file_fails_loudly(tmp_path):
    proc = run("--html", str(tmp_path / "nope.html"))
    assert proc.returncode == 1
    assert "not found" in proc.stderr


def test_usage_error_exits_2():
    assert run().returncode == 2
