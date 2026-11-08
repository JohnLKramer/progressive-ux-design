from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Set

import vocab
from problems import Problem

SLOT_IDS = ("sp-style", "sp-layout")
_REMOTE_PREFIXES = ("http:", "https:", "//")
_ASSET_ATTRS = ("src", "srcset", "poster")
_CSS_URL_NOT_FRAGMENT = re.compile(r"url\((?!\s*['\"]?\s*#)", re.IGNORECASE)


def _is_remote(value: Optional[str]) -> bool:
    return bool(value) and value.strip().lower().startswith(_REMOTE_PREFIXES)


def _srcset_urls(value: str) -> List[str]:
    """Candidate URLs of a srcset, parsed like the HTML spec so `data:` commas survive."""
    urls: List[str] = []
    i, n = 0, len(value)
    while i < n:
        while i < n and (value[i].isspace() or value[i] == ","):
            i += 1
        start = i
        while i < n and not value[i].isspace():
            i += 1
        url = value[start:i]
        if not url:
            break
        if url.endswith(","):
            urls.append(url.rstrip(","))
            continue
        urls.append(url)
        while i < n and value[i] != ",":  # skip descriptors
            i += 1
    return urls


class _Scanner(HTMLParser):
    def __init__(self, roles: frozenset) -> None:
        super().__init__(convert_charrefs=True)
        self.roles = roles
        self.problems: List[Problem] = []
        self.data_el: Set[str] = set()
        self.slots: Set[str] = set()

    def _where(self) -> str:
        line, col = self.getpos()
        return "line %d:%d" % (line, col)

    def _add(self, code: str, message: str) -> None:
        self.problems.append(Problem(code, self._where(), message))

    def handle_starttag(self, tag, attrs) -> None:
        attr = {}
        for name, value in attrs:
            name = name.lower()
            if name in attr:
                self._add("duplicate-attr", "%s given twice on <%s>; browsers keep the first" % (name, tag))
            attr.setdefault(name, value)

        if tag == "script":
            self._add("script", "<script> is not allowed")
        elif tag == "style":
            self._add("style-tag", "<style> is not allowed")

        if "style" in attr:
            self._add("inline-style", "style attribute on <%s>" % tag)
        for name in attr:
            if name.startswith("on"):
                self._add("event-handler", "%s attribute on <%s>" % (name, tag))

        remote_attrs = list(_ASSET_ATTRS)
        if tag == "link":
            remote_attrs.append("href")
            if attr.get("id") in SLOT_IDS:
                self.slots.add(attr["id"])
        for name in remote_attrs:
            value = attr.get(name)
            candidates = _srcset_urls(value) if name == "srcset" and value else [value]
            for candidate in candidates:
                if _is_remote(candidate):
                    self._add("remote-asset", "remote %s on <%s>: %s" % (name, tag, candidate))

        for name, value in attr.items():
            if value and _CSS_URL_NOT_FRAGMENT.search(value):
                self._add("remote-asset", "url() in %s on <%s>: %s" % (name, tag, value[:80]))

        if "data-sp" in attr and attr["data-sp"] not in self.roles:
            self._add("bad-role", "unknown data-sp role %r" % attr["data-sp"])

        el = attr.get("data-el")
        if el:
            self.data_el.add(el)

def _scan(html_path: Path) -> _Scanner:
    scanner = _Scanner(vocab.load_roles())
    scanner.feed(Path(html_path).read_text(encoding="utf-8"))
    scanner.close()
    return scanner


def collect_data_el(html_path: Path) -> Set[str]:
    return _scan(html_path).data_el


def validate_page(html_path: Path, source_el_ids: Optional[Set[str]] = None) -> List[Problem]:
    scanner = _scan(html_path)
    problems = list(scanner.problems)
    for slot in SLOT_IDS:
        if slot not in scanner.slots:
            problems.append(Problem("missing-slot", str(html_path), "missing <link id=\"%s\">" % slot))
    if source_el_ids is not None:
        for el in sorted(source_el_ids - scanner.data_el):
            problems.append(Problem("lost-data-el", str(html_path), "data-el %s missing from page" % el))
    return problems
