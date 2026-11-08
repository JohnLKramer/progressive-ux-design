from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import html_tree  # noqa: E402
from html_tree import Element, Node  # noqa: E402

USAGE = "usage: outline_page.py <page.html> [--max-depth N]"
MAX_LINES = 400
SNIPPET_MAX = 60
LANDMARKS = frozenset("header nav main aside footer section article form".split())
_UNSAFE = re.compile(r"[^\w.:\-]")


def _safe(value: str, limit: int = 40) -> str:
    """Attribute values are untrusted text going to a model: keep a tame alphabet."""
    return _UNSAFE.sub("_", value)[:limit]


def _snippet(el: Element) -> str:
    text = " ".join(" ".join(c.split()) for c in el.children if isinstance(c, str)).strip()
    text = text.replace("<", " ").replace(">", " ").replace('"', "'")
    text = " ".join(text.split())
    if not text:
        return ""
    if len(text) >= SNIPPET_MAX:
        text = text[: SNIPPET_MAX - 4].rstrip() + "..."
    return ' "%s"' % text


def _visible_children(el: Element) -> List[Element]:
    return [
        c for c in el.children if isinstance(c, Element) and c.tag not in html_tree.INVISIBLE_TAGS
    ]


def _signature(el: Element) -> Tuple:
    return (el.tag, tuple(_signature(c) for c in _visible_children(el)))


def _label(el: Element) -> str:
    tag = _safe(el.tag)
    parts = [("* " if el.tag in LANDMARKS else "") + tag]
    for attr, shown in (("id", "#%s"), ("data-el", "data-el=%s"), ("data-sp", "data-sp=%s")):
        value = el.get(attr)
        if value:
            parts.append(shown % _safe(value))
    return " ".join(parts)


def _walk(el: Element, depth: int, max_depth: int, lines: List[str]) -> None:
    children = _visible_children(el)
    index = 0
    while index < len(children):
        child = children[index]
        sig = _signature(child)
        run = 1
        while index + run < len(children) and _signature(children[index + run]) == sig:
            run += 1
        line = "  " * depth + _label(child) + _snippet(child)
        if run > 1:
            line += " ×%d" % run
        grandchildren = _visible_children(child)
        if grandchildren and depth + 1 >= max_depth:
            line += " …"
        lines.append(line)
        if depth + 1 < max_depth:
            _walk(child, depth + 1, max_depth, lines)
        index += run


def _head_titles(nodes: List[Node]) -> List[Element]:
    """<title> elements outside <noscript>/<template>, which are inert or script-only."""
    found: List[Element] = []
    for node in nodes:
        if not isinstance(node, Element) or node.tag in ("noscript", "template"):
            continue
        if node.tag == "title":
            found.append(node)
        found.extend(_head_titles(node.children))
    return found


def outline(page_html: Path, max_depth: int = 6) -> str:
    doc = html_tree.parse(Path(page_html).read_text(encoding="utf-8"))
    lines: List[str] = []
    for el in _head_titles(doc.head):
        lines.append("title" + _snippet(el))
    _walk(doc.body, 0, max_depth, lines)
    if len(lines) > MAX_LINES:
        omitted = len(lines) - (MAX_LINES - 1)
        lines = lines[: MAX_LINES - 1] + ["... %d more lines omitted" % omitted]
    return "\n".join(lines)


def _parse_args(argv: List[str]) -> Optional[Tuple[Path, int]]:
    depth = 6
    rest = list(argv)
    if "--max-depth" in rest:
        i = rest.index("--max-depth")
        if i + 1 >= len(rest) or not rest[i + 1].isdigit() or int(rest[i + 1]) < 1:
            return None
        depth = int(rest[i + 1])
        del rest[i : i + 2]
    if len(rest) != 1:
        return None
    return Path(rest[0]), depth


def main(argv: List[str]) -> int:
    parsed = _parse_args(argv)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    path, depth = parsed
    if not path.is_file():
        print("error: not a file: %s (%s)" % (path, USAGE), file=sys.stderr)
        return 2
    print(outline(path, depth))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
