"""Measure characters per rendered line for the text blocks of a page (rule T3 of aesthetic-rules.md).

Loads the page in a browser in untrusted mode (no scripts run, no remote loads), then counts the
characters, spaces included, that sit on each rendered line of every paragraph-like block. Prints a
JSON list, one object per block:

  selector     tag, id (or data-el) and classes, e.g. `p#intro` or `li.perk`
  text         the first 40 characters, to find the block
  font_px      computed font size
  lines        rendered line count
  line_chars   characters on each line, in order
  max_chars    longest of the full lines (every line but the last)
  median_chars median of the full lines
  t3           "ok", "too-long" (a full line over 90), "too-short" (median full line under 45),
               or "one-line" (a single line is exempt)

Runs as plain `python3`, not `-I`: Playwright lives in user site-packages.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

_HERE = Path(__file__).resolve().parent
for _p in (
    _HERE.parent.parent / "style-switcher" / "scripts",
    _HERE.parent.parent / "design-refine" / "scripts",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from screenshot import _open_page, playwright_available  # noqa: E402

EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NO_PLAYWRIGHT = 3
MIN_CHARS = 45
MAX_CHARS = 90

# Leaf blocks only: a block that contains another block is skipped, so nested text is counted once.
MEASURE_JS = """
() => {
  const BLOCKS = "p,li,blockquote,dd,figcaption,td,th";
  const selectorOf = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    else if (el.getAttribute("data-el")) s += '[data-el="' + el.getAttribute("data-el") + '"]';
    for (const c of el.classList) s += "." + c;
    return s;
  };
  const out = [];
  for (const el of document.querySelectorAll(BLOCKS)) {
    if (el.querySelector(BLOCKS)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const lines = [];
    let prevBottom = null;
    let node;
    const range = document.createRange();
    while ((node = walker.nextNode())) {
      const text = node.nodeValue;
      for (let i = 0; i < text.length; i++) {
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        const rects = range.getClientRects();
        if (!rects.length || rects[0].width === 0) continue;
        const r = rects[0];
        if (prevBottom === null || r.top >= prevBottom - 1) lines.push(0);
        lines[lines.length - 1] += 1;
        prevBottom = r.bottom;
      }
    }
    if (!lines.length) continue;
    out.push({
      selector: selectorOf(el),
      text: el.textContent.trim().replace(/\\s+/g, " ").slice(0, 40),
      font_px: parseFloat(cs.fontSize),
      line_chars: lines,
    });
  }
  return out;
}
"""


def classify(line_chars: List[int]) -> dict:
    full = line_chars[:-1]
    if not full:
        return {"max_chars": line_chars[0], "median_chars": line_chars[0], "t3": "one-line"}
    median = statistics.median(full)
    longest = max(full)
    if longest > MAX_CHARS:
        verdict = "too-long"
    elif median < MIN_CHARS:
        verdict = "too-short"
    else:
        verdict = "ok"
    return {"max_chars": longest, "median_chars": median, "t3": verdict}


def measure(url: str, width: int) -> List[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        page = _open_page(pw, width, 900, True, url=url)
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            raw = page.evaluate(MEASURE_JS)
        finally:
            page.context.browser.close()
    blocks = []
    for item in raw:
        block = {
            "selector": item["selector"],
            "text": item["text"],
            "font_px": item["font_px"],
            "lines": len(item["line_chars"]),
            "line_chars": item["line_chars"],
        }
        block.update(classify(item["line_chars"]))
        blocks.append(block)
    return blocks


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="measure_line_length.py")
    parser.add_argument("--html", help="a page file to measure as it is")
    parser.add_argument("--workspace", help="a style-switcher workspace folder")
    parser.add_argument("--slug", help="the workspace page to measure")
    parser.add_argument("--style", help="the workspace style to apply")
    parser.add_argument("--width", type=int, default=1280, help="viewport width in px")
    args = parser.parse_args(argv)  # argparse exits 2 on usage errors
    by_workspace = args.workspace or args.slug or args.style
    if bool(args.html) == bool(by_workspace) or (by_workspace and not (args.workspace and args.slug and args.style)):
        parser.error("give --html FILE, or --workspace, --slug and --style together")
    if not playwright_available():
        sys.stderr.write("Playwright is not available\n")
        return EXIT_NO_PLAYWRIGHT
    try:
        if args.html:
            page = Path(args.html)
            if not page.is_file():
                raise FileNotFoundError("page not found: %s" % page)
            blocks = measure(page.resolve().as_uri(), args.width)
        else:
            from render import build_styled_copy

            with tempfile.TemporaryDirectory(prefix="measure-line-length-") as tmp:
                styled = build_styled_copy(Path(args.workspace), args.slug, args.style, Path(tmp) / "copy")
                blocks = measure(styled.resolve().as_uri(), args.width)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
        sys.stderr.write("measure failed: %s\n" % " ".join(str(e).split()))
        return EXIT_FAILED
    json.dump(blocks, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
