"""Gates for the design-refine loop.

Marker diff: the (attr, value) markers in a page are its structural contract. Moving
elements or adding wrappers is fine; any change to the multiset of markers is reported.
A missing or unreadable file raises; it is never treated as "no markers".
"""
from __future__ import annotations

import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent.parent / "style-switcher" / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from problems import Problem  # noqa: E402

MARKER_ATTRS = ("data-el", "data-action", "data-exit", "data-variant")


class _MarkerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.markers = Counter()  # type: Counter

    def _scan(self, attrs) -> None:
        for name, value in attrs:
            if name in MARKER_ATTRS:
                self.markers[(name, value if value is not None else "")] += 1

    def handle_starttag(self, tag, attrs) -> None:
        self._scan(attrs)

    def handle_startendtag(self, tag, attrs) -> None:
        self._scan(attrs)


def collect_markers(html_path: Path) -> Counter:
    text = Path(html_path).read_text(encoding="utf-8")
    parser = _MarkerParser()
    parser.feed(text)
    parser.close()
    return parser.markers


def marker_diff(before_html: Path, after_html: Path) -> List[Problem]:
    before = collect_markers(before_html)
    after = collect_markers(after_html)
    problems = []  # type: List[Problem]
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key, 0), after.get(key, 0)
        if a < b:
            problems.append(_problem("marker-lost", after_html, key, b, a))
        elif a > b:
            problems.append(_problem("marker-added", after_html, key, b, a))
    return problems


def _problem(code: str, where: Path, key: Tuple[str, str], before: int, after: int) -> Problem:
    attr, value = key
    return Problem(
        code,
        str(where),
        '%s="%s" count changed from %d to %d' % (attr, value, before, after),
    )
