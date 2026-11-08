"""Strip a saved web page down to bare structure for restyling (untrusted input).

Output is `<dest>/index.html` plus `<dest>/assets/`; nothing else in dest is touched.

Dropped on purpose (and listed in the report):
- Scripts, styles, iframes, objects, remote or tracker images, inline handlers,
  classes, inline styles, vendor attributes.
- References that are not under `<stem>_files/` next to the source: remote URLs,
  absolute paths, `file:` URLs and relative paths pointing anywhere else are dropped
  and listed in `removed_remote` (they cannot be localized).
- URL attributes (href, xlink:href, action, formaction, src, poster, data) whose scheme,
  after removing whitespace and control characters, is not http, https, mailto, tel
  (fragments and relative paths are kept); `data:image/*` is kept on `img` src and
  srcset. Listed in `removed_unsafe`.
- Any attribute whose `url(...)` points anywhere but a `#fragment`, a backslash-escaped
  `url(`, and `xml:base` (listed in `removed_remote` / `removed_unsafe`).
- SVG/MathML animation and foreign content (set, animate, animateTransform,
  animateMotion, foreignObject) and the attributes to/values/from/by.

Fails fast (StripError, nothing written) on: a reference escaping `<stem>_files/`, a
missing local file, a symlinked `<stem>_files`, or a dropped element that carries
`data-el` (generated mockups must not silently lose ids).

Known limit: nesting deeper than the interpreter recursion limit raises RecursionError.
"""
from __future__ import annotations

import os
import posixpath
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import html_tree  # noqa: E402
from html_tree import Element, Node  # noqa: E402
from validate_page import collect_data_el  # noqa: E402

USAGE = "usage: strip_page.py <src.html> <dest_dir>"

ALWAYS_DROP = frozenset(
    "script style noscript template link base iframe frame frameset object embed applet".split()
)
_REMOTE_PREFIXES = ("http:", "https:", "//")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
_ASSET_ATTRS = ("src", "srcset", "poster")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-]")
_CONTROL = re.compile(r"[\x00-\x20\x7f]")
_ALLOWED_SCHEMES = frozenset({"http", "https", "mailto", "tel"})
_URL_ATTRS = frozenset({"href", "xlink:href", "action", "formaction", "src", "poster", "data"})
_FOREIGN_ROOTS = frozenset({"svg", "math"})
_FOREIGN_DROP = frozenset({"set", "animate", "animatetransform", "animatemotion", "foreignobject"})
_FOREIGN_DROP_ATTRS = frozenset({"to", "values", "from", "by"})
_UNSAFE_SHOWN = 80
_CSS_URL = re.compile(r"url\(\s*(?:\"([^\"]*)\"?|'([^']*)'?|([^)]*))", re.IGNORECASE)
_ESCAPED_URL = re.compile(r"[u\\][^()]{0,24}[l\\][^()]{0,8}\(", re.IGNORECASE)

STANDARD_ATTRS = frozenset(
    """abbr accept accept-charset action align alt autocomplete autoplay border cellpadding
    cellspacing charset checked cite cols colspan content controls datetime decoding dir
    disabled download enctype for form formaction headers height hidden high href hreflang
    inputmode kind label lang list loading loop low max maxlength media method min minlength
    multiple muted name novalidate open optimum pattern placeholder playsinline poster preload
    readonly rel required reversed role rows rowspan scope selected shape size sizes span
    spellcheck src srcset start step summary tabindex target title translate type usemap
    value width wrap""".split()
)
# Attributes whose value is one or more element ids (or `#id` for hrefs/usemap).
_IDREF_ATTRS = frozenset(
    "for form list headers aria-labelledby aria-describedby aria-controls aria-owns "
    "aria-flowto aria-details aria-activedescendant aria-errormessage".split()
)
_FRAGMENT_ATTRS = frozenset({"href", "usemap", "xlink:href"})


def _normalize_url(value: str) -> str:
    """How a browser reads the scheme: tabs, newlines, spaces and controls vanish."""
    return _CONTROL.sub("", value)


def _scheme(normalized: str) -> Optional[str]:
    match = _SCHEME.match(normalized)
    return match.group(0)[:-1].lower() if match else None


def _is_unsafe(normalized: str, allow_data_image: bool) -> bool:
    scheme = _scheme(normalized)
    if scheme is None or scheme in _ALLOWED_SCHEMES:
        return False
    return not (scheme == "data" and allow_data_image and normalized.lower().startswith("data:image/"))


class StripError(Exception):
    """The source cannot be stripped safely; nothing has been written."""


@dataclass
class StripReport:
    removed_scripts: int = 0
    localized: List[str] = field(default_factory=list)
    removed_remote: List[str] = field(default_factory=list)
    removed_unsafe: List[str] = field(default_factory=list)
    source_el_ids: List[str] = field(default_factory=list)
    words_before: int = 0
    words_after: int = 0


class _Stripper:
    def __init__(self, src_html: Path) -> None:
        self.files_name = src_html.stem + "_files"
        raw_files_dir = src_html.parent / self.files_name
        if raw_files_dir.is_symlink():
            raise StripError("%s is a symlink; refusing to read through it" % self.files_name)
        self.files_dir = raw_files_dir.resolve()
        self.report = StripReport()
        self.copies: Dict[str, Path] = {}  # asset name -> source file
        self._names_by_file: Dict[Path, str] = {}
        self._folded_names: Set[str] = set()  # case-insensitive: macOS volumes fold case

    # ---- url handling -------------------------------------------------

    def _note_remote(self, url: str) -> None:
        if url not in self.report.removed_remote:
            self.report.removed_remote.append(url)

    def _note_unsafe(self, normalized: str) -> None:
        shown = normalized[:_UNSAFE_SHOWN]
        if shown not in self.report.removed_unsafe:
            self.report.removed_unsafe.append(shown)

    def _keep_css_urls(self, value: str) -> bool:
        """False when the value fetches anything but a `#fragment` through `url(...)`."""
        lowered = value.lower()
        if "\\" in value and _ESCAPED_URL.search(value):  # u\72l( and friends: not decoded
            self._note_remote(value[:_UNSAFE_SHOWN])
            return False
        if "url(" not in lowered:
            return True
        keep = True
        for match in _CSS_URL.finditer(value):
            arg = next(group for group in match.groups() if group is not None).strip().strip("\"'").strip()
            if arg.startswith("#"):
                continue
            keep = False
            normalized = _normalize_url(arg)
            if normalized and _scheme(normalized) in ("javascript", "vbscript", "data"):
                self._note_unsafe(normalized)
            elif arg:
                self._note_remote(arg)
        return keep

    def _asset_name(self, target: Path) -> str:
        if target in self._names_by_file:
            return self._names_by_file[target]
        base = _SAFE_NAME.sub("_", target.name) or "asset"
        name, n = base, 1
        while name.casefold() in self._folded_names:
            n += 1
            stem, dot, ext = base.rpartition(".")
            name = "%s-%d.%s" % (stem, n, ext) if dot and stem else "%s-%d" % (base, n)
        self._names_by_file[target] = name
        self._folded_names.add(name.casefold())
        self.copies[name] = target
        self.report.localized.append("assets/" + name)
        return name

    def resolve(self, url: str, allow_data_image: bool = False) -> Tuple[str, str]:
        """Classify a reference: ("keep", url) | ("local", "assets/<name>") | ("drop", url)."""
        value = url.strip()
        normalized = _normalize_url(value)
        lowered = normalized.lower()
        if not normalized:
            return "drop", ""
        scheme = _scheme(normalized)
        if scheme == "file":  # unresolvable, like any reference outside <stem>_files/
            self._note_remote(value)
            return "drop", value
        if _is_unsafe(normalized, allow_data_image):
            self._note_unsafe(normalized)
            return "drop", value
        if lowered.startswith(_REMOTE_PREFIXES):
            self._note_remote(value)
            return "drop", value
        if scheme == "data":
            return "keep", value
        if scheme is not None or value.startswith("/"):
            self._note_remote(value)
            return "drop", value
        path = unquote(re.split(r"[?#]", value, maxsplit=1)[0])
        while path.startswith("./"):  # browsers write ./<stem>_files/x
            path = path[2:]
        prefix = self.files_name + "/"
        if not path.startswith(prefix):
            self._note_remote(value)  # relative to something we never read
            return "drop", value
        target = (self.files_dir / posixpath.normpath(path[len(prefix):])).resolve()
        if self.files_dir != target and self.files_dir not in target.parents:
            raise StripError("reference escapes %s/: %s" % (self.files_name, value))
        if not target.is_file():
            raise StripError("referenced file is missing: %s" % value)
        return "local", "assets/" + self._asset_name(target)

    def _srcset(self, value: str) -> Tuple[str, bool]:
        """Rewrite each candidate; returns (new srcset, any candidate dropped)."""
        kept: List[str] = []
        dropped = False
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
                url, descriptor = url.rstrip(","), ""
            else:
                dstart = i
                while i < n and value[i] != ",":
                    i += 1
                descriptor = value[dstart:i].strip()
            kind, new = self.resolve(url, allow_data_image=True)
            if kind == "drop":
                dropped = True
                continue
            kept.append(new + (" " + descriptor if descriptor else ""))
        return ", ".join(kept), dropped

    # ---- tree rewriting -----------------------------------------------

    @staticmethod
    def _forbid_data_el(dropped: Element) -> None:
        for el in html_tree.iter_elements([dropped]):
            value = el.get("data-el")
            if value is not None:
                raise StripError("element <%s data-el=%s> would be dropped" % (el.tag, value))

    def _is_tracker(self, el: Element) -> bool:
        return el.tag == "img" and all(
            (el.get(dim) or "").strip().lower() in ("1", "1px") for dim in ("width", "height")
        )

    def _filter_attrs(self, el: Element, in_svg: bool) -> Optional[List[Tuple[str, str]]]:
        """New attribute list, or None when the element itself must go."""
        out: List[Tuple[str, str]] = []
        for name, value in el.attrs:
            if name in ("class", "style", "xml:base") or name.startswith("on"):
                continue
            if not (
                name == "id"
                or name.startswith("data-")
                or name.startswith("aria-")
                or name in STANDARD_ATTRS
                or in_svg
            ):
                continue
            if in_svg and name in _FOREIGN_DROP_ATTRS:
                continue
            if not self._keep_css_urls(value):
                continue
            is_asset = name in _ASSET_ATTRS or (
                in_svg
                and el.tag != "a"  # links follow the same allowlist as html links
                and name in ("href", "xlink:href")
                and not value.strip().startswith("#")
            )
            if not is_asset:
                if name in _URL_ATTRS:
                    normalized = _normalize_url(value)
                    if _is_unsafe(normalized, False):
                        self._note_unsafe(normalized)
                        continue
                out.append((name, value))
                continue
            if name == "srcset":
                new, _ = self._srcset(value)
                if new:
                    out.append((name, new))
                continue
            kind, new = self.resolve(value, allow_data_image=el.tag == "img" and name == "src")
            if kind == "drop":
                if el.tag == "img" and name == "src":
                    return None
                continue
            out.append((name, new))
        if el.tag == "img" and not any(n in ("src", "srcset") for n, _ in out):
            if any(n in ("src", "srcset") for n, _ in el.attrs):
                return None
        return out

    def _rewrite(self, nodes: List[Node], in_svg: bool) -> List[Node]:
        out: List[Node] = []
        for node in nodes:
            if isinstance(node, str):
                out.append(node)
                continue
            if node.tag in ALWAYS_DROP:
                self._forbid_data_el(node)
                if node.tag == "script":
                    self.report.removed_scripts += 1
                elif node.tag in ("iframe", "frame", "embed"):
                    src = node.get("src")
                    if src and src.strip().lower().startswith(_REMOTE_PREFIXES):
                        self._note_remote(src.strip())
                elif node.tag == "link":
                    href = node.get("href")
                    if href and href.strip().lower().startswith(_REMOTE_PREFIXES):
                        self._note_remote(href.strip())
                continue
            if in_svg and node.tag in _FOREIGN_DROP:
                self._forbid_data_el(node)
                continue
            if self._is_tracker(node):
                self._forbid_data_el(node)
                src = node.get("src")
                if src and src.strip().lower().startswith(_REMOTE_PREFIXES):
                    self._note_remote(src.strip())
                continue
            svg = in_svg or node.tag in _FOREIGN_ROOTS
            attrs = self._filter_attrs(node, svg)
            if attrs is None:
                self._forbid_data_el(node)
                continue
            clean = Element(node.tag, attrs)
            clean.children = self._rewrite(node.children, svg)
            out.append(clean)
        return out

    def _head(self, nodes: List[Node]) -> List[Element]:
        kept: List[Element] = []
        for node in self._rewrite(nodes, False):
            if not isinstance(node, Element):
                continue
            if node.tag == "title":
                if node.get("data-el") is not None:  # rebuilt below without attributes
                    raise StripError("element <title data-el=%s> would be dropped" % node.get("data-el"))
                kept.append(Element("title", []))
                kept[-1].children = node.children
                continue
            name = node.get("name")
            if (
                node.tag == "meta"
                and name
                and node.get("content") is not None
                and name.lower() != "refresh"
                and node.get("data-el") is None
            ):
                kept.append(Element("meta", [("name", name), ("content", node.get("content") or "")]))
            else:
                self._forbid_data_el(node)
        return kept


def _referenced_ids(nodes: List[Node]) -> Set[str]:
    refs: Set[str] = set()
    for el in html_tree.iter_elements(nodes):
        for name, value in el.attrs:
            if name in _IDREF_ATTRS:
                refs.update(value.split())
            elif name in _FRAGMENT_ATTRS and value.startswith("#") and len(value) > 1:
                refs.add(value[1:])
    return refs


def _drop_unreferenced_ids(nodes: List[Node], refs: Set[str]) -> None:
    for el in html_tree.iter_elements(nodes):
        el.attrs = [(n, v) for n, v in el.attrs if n != "id" or v in refs]


def _top_attrs(attrs, allowed) -> List[Tuple[str, str]]:
    return [(n, v) for n, v in attrs if n in allowed or n.startswith(("data-", "aria-"))]


def _render(doc_lang: List[Tuple[str, str]], head: List[Element], body: Element) -> str:
    parts = ["<!DOCTYPE html>\n<html"]
    for name, value in doc_lang:
        parts.append(' %s="%s"' % (name, html_tree.escape_attr(value)))
    parts.append(">\n<head>\n<meta charset=\"utf-8\">\n")
    for el in head:
        parts.append(html_tree.serialize(el) + "\n")
    parts.append('<link id="sp-style" rel="stylesheet">\n<link id="sp-layout" rel="stylesheet">\n</head>\n')
    parts.append(html_tree.serialize(body))
    parts.append("\n</html>\n")
    return "".join(parts)


def strip_page(src_html: Path, dest_dir: Path) -> StripReport:
    src_html, dest_dir = Path(src_html), Path(dest_dir)
    try:
        source = src_html.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise StripError("source is not valid utf-8: %s" % exc) from exc
    if (dest_dir / "index.html").exists() and (dest_dir / "index.html").resolve() == src_html.resolve():
        raise StripError("destination index.html is the source file")

    doc = html_tree.parse(source)
    stripper = _Stripper(src_html)
    report = stripper.report
    report.words_before = html_tree.count_visible_words(doc.head + [doc.body])
    report.source_el_ids = sorted(collect_data_el(src_html))

    head = stripper._head(doc.head)
    body = Element("body", [])
    body.children = stripper._rewrite(doc.body.children, False)
    body.attrs = _top_attrs(stripper._filter_attrs(doc.body, False) or [], ("id",))
    nodes: List[Node] = list(head) + [body]
    _drop_unreferenced_ids(nodes, _referenced_ids(nodes))
    report.words_after = html_tree.count_visible_words(nodes)
    html_attrs = _top_attrs(doc.html_attrs, ("lang", "dir"))

    output = _render(html_attrs, head, body)

    # Everything above is in memory; only now touch the destination.
    if dest_dir.exists() and not dest_dir.is_dir():
        raise StripError("destination is not a directory: %s" % dest_dir)
    assets = dest_dir / "assets"
    if assets.is_symlink() or (assets.exists() and not assets.is_dir()):
        raise StripError("%s exists and is not a directory" % assets)
    dest_dir.mkdir(parents=True, exist_ok=True)
    staging = dest_dir / ".assets-tmp"
    if staging.is_symlink() or staging.exists():
        if staging.is_symlink() or not staging.is_dir():
            raise StripError("%s exists and is not a directory" % staging)
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        for name, source_file in stripper.copies.items():
            shutil.copyfile(source_file, staging / name)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise StripError("cannot copy asset: %s" % exc) from exc
    if assets.is_dir():
        shutil.rmtree(assets)
    os.rename(staging, assets)
    with open(dest_dir / "index.html", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(output)
    return report


def _format_report(src: Path, dest: Path, report: StripReport) -> str:
    kept = 100.0 * report.words_after / report.words_before if report.words_before else 100.0
    lines = [
        "stripped %s -> %s" % (src, dest / "index.html"),
        "removed scripts: %d" % report.removed_scripts,
        "localized assets: %d" % len(report.localized),
        "removed remote/unresolved references: %d" % len(report.removed_remote),
    ]
    lines += ["  " + url for url in report.removed_remote]
    lines.append("removed unsafe urls: %d" % len(report.removed_unsafe))
    lines += ["  " + url for url in report.removed_unsafe]
    lines += [
        "source data-el ids: %d" % len(report.source_el_ids),
        "words: %d -> %d (%.1f%% kept)" % (report.words_before, report.words_after, kept),
    ]
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    src, dest = Path(argv[0]), Path(argv[1])
    if not src.is_file():
        print("error: source is not a file: %s (%s)" % (src, USAGE), file=sys.stderr)
        return 2
    if dest.exists() and not dest.is_dir():
        print("error: destination is not a directory: %s (%s)" % (dest, USAGE), file=sys.stderr)
        return 2
    try:
        report = strip_page(src, dest)
    except StripError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print(_format_report(src, dest, report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
