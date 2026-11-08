"""Small tolerant HTML tree builder on top of html.parser (no third-party parser).

Text is stored decoded; `escape_text` / `escape_attr` re-encode on output so text
round-trips. The page is split into `html` attributes, head nodes and a body element
the way a browser would (implicit head, implicit body).
"""
from __future__ import annotations

import html
from html.entities import html5
from html.parser import HTMLParser
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)
HEAD_TAGS = frozenset("title meta link base script style noscript template".split())
_BLOCK_CLOSES_P = frozenset(
    "address article aside blockquote details div dl fieldset figcaption figure footer "
    "form h1 h2 h3 h4 h5 h6 header hgroup hr main menu nav ol p pre section table ul".split()
)
_AUTOCLOSE: Dict[str, frozenset] = {
    "li": frozenset({"li"}),
    "dt": frozenset({"dt", "dd"}),
    "dd": frozenset({"dt", "dd"}),
    "tr": frozenset({"tr", "td", "th"}),
    "td": frozenset({"td", "th"}),
    "th": frozenset({"td", "th"}),
    "option": frozenset({"option"}),
    "thead": frozenset({"tbody", "tfoot", "tr", "td", "th"}),
    "tbody": frozenset({"thead", "tbody", "tfoot", "tr", "td", "th"}),
    "tfoot": frozenset({"thead", "tbody", "tr", "td", "th"}),
}


class Element:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: List["Node"] = []

    def get(self, name: str) -> Optional[str]:
        for key, value in self.attrs:
            if key == name:
                return value
        return None


Node = Union[Element, str]


class Document:
    def __init__(self) -> None:
        self.html_attrs: List[Tuple[str, str]] = []
        self.head: List[Node] = []
        self.body = Element("body", [])


def _dedupe(attrs) -> List[Tuple[str, str]]:
    seen: Set[str] = set()
    out: List[Tuple[str, str]] = []
    for name, value in attrs:
        name = name.lower()
        if name in seen:
            continue
        seen.add(name)
        out.append((name, value if value is not None else ""))
    return out


def _append_text(children: List[Node], text: str) -> None:
    if children and isinstance(children[-1], str):
        children[-1] = children[-1] + text
    else:
        children.append(text)


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.doc = Document()
        self.mode = "head"  # browsers start in an implicit head
        self.head_root = Element("head", [])
        self.stack: List[Element] = [self.head_root]

    def _enter_body(self) -> None:
        self.mode = "body"
        self.stack = [self.doc.body]

    def handle_starttag(self, tag, attrs) -> None:
        tag = tag.lower()
        attrs = _dedupe(attrs)
        if tag == "html":
            if not self.doc.html_attrs:
                self.doc.html_attrs = attrs
            return
        if tag == "head":
            return
        if tag == "body":
            if self.mode == "head":
                self._enter_body()
            if not self.doc.body.attrs:
                self.doc.body.attrs = attrs
            return
        if self.mode == "head" and len(self.stack) == 1 and tag not in HEAD_TAGS:
            self._enter_body()
        if tag == "p" or tag in _AUTOCLOSE or tag in _BLOCK_CLOSES_P:
            self._autoclose(tag)
        element = Element(tag, attrs)
        self.stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def _autoclose(self, tag: str) -> None:
        closes = _AUTOCLOSE.get(tag, frozenset())
        while len(self.stack) > 1:
            top = self.stack[-1].tag
            if top in closes or (top == "p" and tag in _BLOCK_CLOSES_P):
                self.stack.pop()
            else:
                break

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)
        tag = tag.lower()
        if tag not in VOID_TAGS and tag not in ("html", "head", "body") and len(self.stack) > 1:
            if self.stack[-1].tag == tag:
                self.stack.pop()

    def handle_endtag(self, tag) -> None:
        tag = tag.lower()
        if tag == "head":
            if self.mode == "head":
                self._enter_body()
            return
        if tag in ("html", "body") or tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def _text(self, text: str) -> None:
        if self.mode == "head" and len(self.stack) == 1:
            if not text.strip():
                return
            self._enter_body()
        _append_text(self.stack[-1].children, text)

    def handle_data(self, data) -> None:
        self._text(data)

    def handle_entityref(self, name) -> None:
        # html.unescape would also expand legacy prefixes (`&notit;` -> `¬it;`); only
        # exact, known entities are decoded, anything else stays literal text.
        self._text(html5.get(name + ";", "&%s;" % name))

    def handle_charref(self, name) -> None:
        self._text(html.unescape("&#%s;" % name))

def parse(source: str) -> Document:
    builder = _Builder()
    builder.feed(source)
    builder.close()
    builder.doc.head = builder.head_root.children
    return builder.doc


def escape_text(text: str) -> str:
    return html.escape(text, quote=False).replace("\u00a0", "&nbsp;")


def escape_attr(value: str) -> str:
    return html.escape(value, quote=True).replace("\u00a0", "&nbsp;")


def serialize(node: Node) -> str:
    parts: List[str] = []
    _serialize(node, parts)
    return "".join(parts)


def _serialize(node: Node, parts: List[str]) -> None:
    if isinstance(node, str):
        parts.append(escape_text(node))
        return
    parts.append("<" + node.tag)
    for name, value in node.attrs:
        parts.append(' %s="%s"' % (name, escape_attr(value)))
    parts.append(">")
    if node.tag in VOID_TAGS:
        return
    if node.tag in ("pre", "textarea", "listing") and node.children:
        first = node.children[0]
        if isinstance(first, str) and first.startswith("\n"):
            parts.append("\n")  # the parser swallows one leading newline
    for child in node.children:
        _serialize(child, parts)
    parts.append("</%s>" % node.tag)


def iter_elements(nodes: List[Node]) -> Iterator[Element]:
    for node in nodes:
        if isinstance(node, Element):
            yield node
            for inner in iter_elements(node.children):
                yield inner


INVISIBLE_TAGS = frozenset({"script", "style", "noscript", "template"})


def count_visible_words(nodes: List[Node], skip_hidden: bool = False) -> int:
    """Words in text nodes. With `skip_hidden`, subtrees carrying a `hidden` attribute do not count."""
    total = 0
    for node in nodes:
        if isinstance(node, str):
            total += len(node.split())
        elif node.tag in INVISIBLE_TAGS:
            continue
        elif skip_hidden and node.get("hidden") is not None:
            continue
        else:
            total += count_visible_words(node.children, skip_hidden)
    return total


HIDDEN_INTERACTIVE_TAGS = frozenset({"form", "input", "select", "textarea"})
HIDDEN_INTERACTIVE_ATTRS = ("data-el", "data-action", "data-exit")


def _is_interactive(node: Element) -> bool:
    return node.tag in HIDDEN_INTERACTIVE_TAGS or any(node.get(a) is not None for a in HIDDEN_INTERACTIVE_ATTRS)


def count_wordless_hidden_interactive(nodes: List[Node]) -> int:
    """Form controls and data-el, data-action or data-exit elements inside a `hidden` subtree that holds no words.

    The word gate already bounds hidden text, so a hidden subtree with words is covered by it. A wordless hidden
    subtree (a bare form, a lone input) would cost the gate nothing, so it is counted here. Wordless buttons and
    links are decoration such as map controls and are not counted."""
    total = 0
    for node in nodes:
        if isinstance(node, str) or node.tag in INVISIBLE_TAGS:
            continue
        if node.get("hidden") is not None and count_visible_words([node]) == 0:
            total += sum(1 for e in [node] + list(iter_elements(node.children)) if _is_interactive(e))
        else:
            total += count_wordless_hidden_interactive(node.children)
    return total


def hidden_flags(nodes: List[Node], hidden: bool = False) -> List[bool]:
    """One flag per visible word and per form control or data-el, data-action, data-exit element, in document order.
    True when it sits in a subtree with a `hidden` attribute (an element's own attribute counts for itself)."""
    flags: List[bool] = []
    for node in nodes:
        if isinstance(node, str):
            flags.extend([hidden] * len(node.split()))
        elif node.tag not in INVISIBLE_TAGS:
            here = hidden or node.get("hidden") is not None
            if _is_interactive(node):
                flags.append(here)
            flags.extend(hidden_flags(node.children, here))
    return flags
