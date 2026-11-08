"""Check that the model's page only gained roles, variants and wrapper divs.

`check_edits(source_html, final_html)` strips the source into a temporary directory and
compares that page with the final page structurally. Before comparing, `data-sp` and
`data-sp-variant` are removed and every `div` left without other attributes is replaced by
its children (on both sides, so a bare div in the source cancels out too). A wrapper div may carry `hidden`. Text is compared
with whitespace runs collapsed; whitespace-only text is ignored.

The `hidden` attribute may be added to an element (a style hides it with `[hidden]`), never
removed. Hidden text still counts as present (`words-lost`), but at least `MIN_VISIBLE_RATIO`
of the source's visible words must stay visible (`words-hidden`); words inside elements the
source itself marked `hidden` count on neither side. A word the source hid must stay hidden
(`unhidden`), and a form control or data-el/data-action/data-exit element may not be hidden inside a
subtree with no words (`hidden-interactive`), because the word gate cannot see it.
"""
from __future__ import annotations

import difflib
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import html_tree  # noqa: E402
from html_tree import Element, Node  # noqa: E402
from problems import Problem  # noqa: E402
from strip_page import StripError, strip_page  # noqa: E402

MODEL_ATTRS = frozenset({"data-sp", "data-sp-variant"})
MAX_REPORTED = 20
MIN_VISIBLE_RATIO = 0.9
_SHOWN = 60


class _N:
    """Normalized node: text (`tag is None`) or element, with a structural signature."""

    __slots__ = ("tag", "text", "attrs", "children", "sig")

    def __init__(self, tag: Optional[str], text: str, attrs: Dict[str, str], children: List["_N"]) -> None:
        self.tag = tag
        self.text = text
        self.attrs = attrs
        self.children = children
        if tag is None:
            self.sig = "T" + repr(text)
        else:
            self.sig = "<%s %r>%s</>" % (tag, sorted(attrs.items()), "".join(c.sig for c in children))


def _attrs(attrs) -> Dict[str, str]:
    return {name: value for name, value in attrs if name not in MODEL_ATTRS}


def _normalize(nodes: List[Node]) -> List[_N]:
    flat: List[object] = []  # str | Element, wrappers replaced by their children

    def collect(items: List[Node]) -> None:
        for node in items:
            if isinstance(node, str):
                flat.append(node)
            elif node.tag == "div" and set(_attrs(node.attrs)) <= {"hidden"}:
                collect(node.children)
            else:
                flat.append(node)

    collect(nodes)
    out: List[_N] = []
    pending: List[str] = []

    def flush() -> None:
        text = " ".join("".join(pending).split())
        pending[:] = []
        if text:
            out.append(_N(None, text, {}, []))

    for node in flat:
        if isinstance(node, str):
            pending.append(node)
            continue
        flush()
        out.append(_N(node.tag, "", _attrs(node.attrs), _normalize(node.children)))
    flush()
    return out


def _short(text: str) -> str:
    return repr(text if len(text) <= _SHOWN else text[:_SHOWN] + "...")


def _label(node: _N) -> str:
    return "text %s" % _short(node.text) if node.tag is None else "<%s>" % node.tag


def _path(parent: str, siblings: List[_N], index: int) -> str:
    node = siblings[index]
    if node.tag is None:
        return parent
    if node.tag == "body":
        return "body"
    position = sum(1 for other in siblings[: index + 1] if other.tag == node.tag)
    return "%s > %s[%d]" % (parent, node.tag, position)


def _diff_children(path: str, a: List[_N], b: List[_N], out: List[Tuple[str, str]]) -> None:
    matcher = difflib.SequenceMatcher(None, [n.sig for n in a], [n.sig for n in b], autojunk=False)
    for op, a1, a2, b1, b2 in matcher.get_opcodes():
        if op == "equal":
            continue
        paired = min(a2 - a1, b2 - b1) if op == "replace" else 0
        for k in range(paired):
            _diff_pair(path, a, a1 + k, b, b1 + k, out)
        for i in range(a1 + paired, a2):
            out.append((_path(path, a, i), "missing %s" % _label(a[i])))
        for j in range(b1 + paired, b2):
            out.append((_path(path, b, j), "extra %s" % _label(b[j])))


def _diff_pair(path: str, a: List[_N], i: int, b: List[_N], j: int, out: List[Tuple[str, str]]) -> None:
    left, right = a[i], b[j]
    where = _path(path, b, j)
    if left.tag is None and right.tag is None:
        out.append((where, "text: %s -> %s" % (_short(left.text), _short(right.text))))
    elif left.tag != right.tag:
        out.append((where, "tag: %s -> %s" % (_label(left), _label(right))))
    else:
        for name in sorted(set(left.attrs) | set(right.attrs)):
            old, new = left.attrs.get(name), right.attrs.get(name)
            if old == new:
                continue
            if name == "hidden" and old is None:
                continue
            if old is None:
                out.append((where, "attribute %s added: %s" % (name, _short(new or ""))))
            elif new is None:
                out.append((where, "attribute %s removed (was %s)" % (name, _short(old))))
            else:
                out.append((where, "attribute %s: %s -> %s" % (name, _short(old), _short(new))))
        _diff_children(where, left.children, right.children, out)


def _compare(source_doc: html_tree.Document, final_doc: html_tree.Document) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    left_html, right_html = _attrs(source_doc.html_attrs), _attrs(final_doc.html_attrs)
    for name in sorted(set(left_html) | set(right_html)):
        if left_html.get(name) != right_html.get(name):
            out.append(("html", "attribute %s: %s -> %s" % (name, _short(left_html.get(name) or ""), _short(right_html.get(name) or ""))))
    _diff_children("head", _normalize(source_doc.head), _normalize(final_doc.head), out)
    left_body = _N("body", "", _attrs(source_doc.body.attrs), _normalize(source_doc.body.children))
    right_body = _N("body", "", _attrs(final_doc.body.attrs), _normalize(final_doc.body.children))
    _diff_pair("", [left_body], 0, [right_body], 0, out)
    return out


def _words(doc: html_tree.Document) -> int:
    return html_tree.count_visible_words(doc.head + [doc.body])


def visible_ratio(before: int, after: int) -> float:
    return 1.0 if before == 0 else after / before


def check_edits(source_html: Path, final_html: Path) -> List[Problem]:
    source_html, final_html = Path(source_html), Path(final_html)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            strip_page(source_html, Path(tmp) / "stripped")
        except StripError as exc:
            return [Problem("strip-failed", str(source_html), str(exc))]
        stripped_text = (Path(tmp) / "stripped" / "index.html").read_text(encoding="utf-8")
    source_doc = html_tree.parse(stripped_text)
    final_doc = html_tree.parse(final_html.read_text(encoding="utf-8"))

    problems: List[Problem] = []
    differences = _compare(source_doc, final_doc)
    for where, message in differences[:MAX_REPORTED]:
        problems.append(Problem("content-changed", where, message))
    if len(differences) > MAX_REPORTED:
        problems.append(Problem("content-changed", "...", "%d more" % (len(differences) - MAX_REPORTED)))
    before, after = _words(source_doc), _words(final_doc)
    if after < before:
        problems.append(Problem("words-lost", str(final_html), "%d visible words, stripped source has %d" % (after, before)))
    shown_before = html_tree.count_visible_words(source_doc.head + [source_doc.body], skip_hidden=True)
    shown_after = html_tree.count_visible_words(final_doc.head + [final_doc.body], skip_hidden=True)
    ratio = visible_ratio(shown_before, shown_after)
    if ratio < MIN_VISIBLE_RATIO:
        problems.append(Problem("words-hidden", str(final_html), "only %d%% of the visible words stay visible (%d of %d); hide less, the minimum is %d%%" % (
            int(ratio * 100), shown_after, shown_before, int(MIN_VISIBLE_RATIO * 100))))
    problems.extend(_hidden_problems(source_doc, final_doc, final_html))
    return problems


def _hidden_problems(source_doc: html_tree.Document, final_doc: html_tree.Document, final_html: Path) -> List[Problem]:
    problems: List[Problem] = []
    source_nodes, final_nodes = source_doc.head + [source_doc.body], final_doc.head + [final_doc.body]
    source_flags, final_flags = html_tree.hidden_flags(source_nodes), html_tree.hidden_flags(final_nodes)
    if any(source_flags):
        if len(source_flags) != len(final_flags):
            problems.append(Problem("unhidden", str(final_html), "cannot match the source's hidden words and controls to the final page (%d against %d); keep text nodes and controls as they are" % (
                len(source_flags), len(final_flags))))
        else:
            shown = sum(1 for before, after in zip(source_flags, final_flags) if before and not after)
            if shown:
                problems.append(Problem("unhidden", str(final_html), "%d words or controls the source hid are visible; a hidden element stays hidden" % shown))
    added = html_tree.count_wordless_hidden_interactive(final_nodes) - html_tree.count_wordless_hidden_interactive(source_nodes)
    if added > 0:
        problems.append(Problem("hidden-interactive", str(final_html),
                                "%d form controls or data-el/data-action/data-exit elements were hidden with no words to count; hide only copies that have words, and wordless decoration" % added))
    return problems
