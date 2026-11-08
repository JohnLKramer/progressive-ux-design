"""Summarise the CSS of a saved style source as compact JSON evidence for a model.

Sources are untrusted: nothing is executed or fetched. Linked stylesheets are read only
when they resolve to a regular file under the source directory (at most 5 MB each).
The output holds tallies of individual declaration values, never raw HTML or CSS rules.

usage: gather_evidence.py <source_dir> <out.json> [--top-n N]
"""
from __future__ import annotations

import colorsys
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import html_tree  # noqa: E402
from unpack import UnpackError, find_pages  # noqa: E402

USAGE = "usage: gather_evidence.py <source_dir> <out.json> [--top-n N]"
MAX_CSS_BYTES = 5 * 1024 * 1024
MAX_PAGE_BYTES = 50 * 1024 * 1024
MAX_JSON_BYTES = 60_000
MAX_STRING = 120
MIN_TOP_N = 5
DEFAULT_TOP_N = 25

FONT_EXTS = (".woff", ".woff2", ".ttf", ".otf", ".eot")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico")
CATEGORIES = ("colors", "fonts", "font_sizes", "radii", "shadows", "spacing")


class EvidenceError(Exception):
    pass


NAMED_COLORS = {
    "aqua": "#00ffff", "black": "#000000", "blue": "#0000ff", "fuchsia": "#ff00ff",
    "gray": "#808080", "green": "#008000", "lime": "#00ff00", "maroon": "#800000",
    "navy": "#000080", "olive": "#808000", "orange": "#ffa500", "purple": "#800080",
    "red": "#ff0000", "silver": "#c0c0c0", "teal": "#008080", "white": "#ffffff",
    "yellow": "#ffff00", "rebeccapurple": "#663399",
}
_NAMED_COLOR_PROPS = frozenset({
    "color", "background", "background-color", "fill", "stroke", "box-shadow", "text-shadow",
    "text-decoration-color", "caret-color", "accent-color", "column-rule-color",
})
_NAMED_COLOR_PREFIXES = ("border", "outline")

# One token at a time: a comment opener, a quote, a backslash escape or `url(`.
_SCAN_RE = re.compile(r"/\*|[\"'\\]|[uU][rR][lL]\(")
_STRING_END_RES = {
    '"': re.compile(r'["\\\n]'),
    "'": re.compile(r"['\\\n]"),
}
_URL_END_RE = re.compile(r"[)\\]")
_SPACE_RE = re.compile(r"\s*")
_SYNTAX_RE = re.compile(r"[{};]")
_VENDOR_PREFIX_RE = re.compile(r"^-(?:webkit|moz|ms|o)-")
_BRACE_RE = re.compile(r"[{}]")
_STRING_RE = re.compile(r"""\"[^\"]*\"|'[^']*'""")
_COLOR_RE = re.compile(
    r"#([0-9a-fA-F]{3,8})(?![\w-])"
    r"|\b(rgba?|hsla?)\(([^()]*)\)"
    r"|(?<![\w#.-])(" + "|".join(sorted(NAMED_COLORS)) + r")(?![\w(.-])",
    re.I,
)
_FONT_SIZE_RE = re.compile(
    r"^(?:\d*\.?\d+(?:px|em|rem|pt|pc|ex|ch|cm|mm|in|q|vw|vh|vmin|vmax|%)|0"
    r"|xx-small|x-small|small|medium|large|x-large|xx-large|xxx-large|smaller|larger)$"
)
_FONT_PREFIX_RE = re.compile(
    r"^(?:normal|italic|oblique|small-caps|bold|bolder|lighter|\d+(?:\.\d+)?|-?\d*\.?\d+deg"
    r"|(?:ultra-|extra-|semi-)?(?:condensed|expanded))$"
)
_LENGTH_RE = re.compile(r"^-?\d*\.?\d+(?:px|rem|em|%)$")
_TOKEN_RE = re.compile(r"\s*(\S+)")
_FONT_SYSTEM = frozenset({"caption", "icon", "menu", "message-box", "small-caption", "status-bar"})
_NOISE_VALUES = frozenset({"0", "0px", "none"})
_RADIUS_RE = re.compile(r"^border(?:-[a-z]+)*-radius$")
_SPACING_RE = re.compile(r"^(?:margin|padding)(?:-[a-z]+)*$|^(?:gap|row-gap|column-gap|grid-gap)$")
_GROUP_AT_RULES = ("@media", "@supports", "@layer", "@container", "@document", "@-moz-document",
                   "@scope", "@starting-style")
_IGNORED_KEYWORDS = frozenset({"inherit", "initial", "unset", "revert", "revert-layer"})


def _clip(value: str) -> str:
    """Keep the head of a value, ending in `…` when clipped (total length <= MAX_STRING)."""
    return value if len(value) <= MAX_STRING else value[: MAX_STRING - 1] + "…"


def _clip_path(value: str) -> str:
    """Keep the tail of a path (the distinguishing part), starting with `…` when clipped."""
    return value if len(value) <= MAX_STRING else "…" + value[-(MAX_STRING - 1):]


def _clean_text(text: str) -> str:
    """Make a path/name safe to encode as utf-8 JSON (undecodable bytes become escapes)."""
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


# ---- colors -----------------------------------------------------------------------


def _number(token: str) -> float:
    token = token.strip().lower()
    if token == "none":
        return 0.0
    return float(token)


def _alpha(token: str) -> float:
    token = token.strip().lower()
    if token.endswith("%"):
        return float(token[:-1]) / 100.0
    return _number(token)


def _channel(token: str) -> int:
    token = token.strip().lower()
    if token.endswith("%"):
        value = float(token[:-1]) * 255.0 / 100.0
    else:
        value = _number(token)
    return max(0, min(255, int(round(value))))


def _hue(token: str) -> float:
    token = token.strip().lower()
    for suffix, factor in (("deg", 1.0), ("grad", 0.9), ("rad", 57.29577951308232), ("turn", 360.0)):
        if token.endswith(suffix):
            return float(token[: -len(suffix)]) * factor
    return _number(token)


def _hex(r: int, g: int, b: int) -> str:
    return "#%02x%02x%02x" % (r, g, b)


def _function_color(name: str, body: str) -> Optional[str]:
    parts = [p for p in re.split(r"[\s,/]+", body.strip()) if p]
    if len(parts) not in (3, 4):
        return None
    try:
        if len(parts) == 4 and _alpha(parts[3]) <= 0:
            return None
        if name.startswith("rgb"):
            return _hex(_channel(parts[0]), _channel(parts[1]), _channel(parts[2]))
        hue = (_hue(parts[0]) % 360.0) / 360.0
        sat = max(0.0, min(1.0, _number(parts[1].rstrip("%")) / 100.0))
        light = max(0.0, min(1.0, _number(parts[2].rstrip("%")) / 100.0))
    except ValueError:
        return None
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return _hex(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def _hex_color(digits: str) -> Optional[str]:
    n = len(digits)
    digits = digits.lower()
    if n in (3, 4):
        if n == 4 and digits[3] == "0":
            return None
        return "#" + "".join(c * 2 for c in digits[:3])
    if n in (6, 8):
        if n == 8 and digits[6:] == "00":
            return None
        return "#" + digits[:6]
    return None


def extract_colors(value: str, allow_named: bool) -> List[str]:
    out: List[str] = []
    for match in _COLOR_RE.finditer(value):
        digits, func, body, named = match.groups()
        if digits is not None:
            color = _hex_color(digits)
        elif func is not None:
            color = _function_color(func.lower(), body)
        elif allow_named:
            color = NAMED_COLORS[named.lower()]
        else:
            color = None
        if color:
            out.append(color)
    return out


def _whole_color(value: str) -> Optional["re.Match[str]"]:
    """The color match when the WHOLE value is a single color (any syntax), else None."""
    return _COLOR_RE.fullmatch(value.strip())


def _whole_color_value(value: str) -> Optional[str]:
    match = _whole_color(value)
    if match is None:
        return None
    digits, func, body, named = match.groups()
    if digits is not None:
        return _hex_color(digits)
    if func is not None:
        return _function_color(func.lower(), body)
    return NAMED_COLORS[named.lower()]


# ---- CSS parsing ------------------------------------------------------------------


class _Parsed:
    """Per-stylesheet tallies; merged per page so shared sheets count once per page."""

    def __init__(self) -> None:
        self.tallies: Dict[str, Counter] = {c: Counter() for c in CATEGORIES}
        self.custom: Dict[str, str] = {}


def _split_tokens(value: str) -> List[str]:
    if "(" not in value:
        return value.split()
    tokens: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _first_family(value: str) -> Optional[str]:
    first = value.split(",", 1)[0].strip().strip("\"'").strip()
    if not first or first.lower() in _IGNORED_KEYWORDS or first.lower().startswith("var("):
        return None
    return first


def _is_noise_value(lowered: str) -> bool:
    """True for values that carry no design information: 0, none, keywords, var()-only."""
    if lowered in _NOISE_VALUES or lowered in _IGNORED_KEYWORDS:
        return True
    tokens = _split_tokens(lowered)
    return bool(tokens) and all(t.rstrip(",").startswith("var(") and t.rstrip(",").endswith(")")
                                for t in tokens)


def _parse_font_shorthand(value: str) -> Optional[Tuple[str, Optional[str]]]:
    """(size, first family) of `font: [style] [variant] [weight] size[/lh] family, ...`, or None."""
    text = value.strip()
    if not text or text.lower() in _FONT_SYSTEM or text.lower() in _IGNORED_KEYWORDS:
        return None
    pos = 0
    for _ in range(6):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            return None
        token = match.group(1)
        pos = match.end()
        size, slash, line_height = token.partition("/")
        if _FONT_SIZE_RE.match(size.lower()):
            if slash and not line_height:
                skip = _TOKEN_RE.match(text, pos)
                pos = skip.end() if skip else pos
            elif not slash:
                gap = _SPACE_RE.match(text, pos).end()
                if text.startswith("/", gap):
                    skip = _TOKEN_RE.match(text, gap + 1)
                    pos = skip.end() if skip else len(text)
            family = _first_family(text[pos:])
            return (size.lower(), family) if text[pos:].strip() else None
        if not _FONT_PREFIX_RE.match(token.lower()):
            return None
    return None


def _strip_important(value: str) -> str:
    value = value.strip()
    if value[-10:].lower() == "!important":
        value = value[:-10].rstrip()
    return value


def _declaration(parsed: _Parsed, name: str, value: str, in_font_face: bool) -> None:
    name = name.strip()
    value = _strip_important(value)
    if not name or not value:
        return
    if in_font_face:
        if name.lower() == "font-family":
            family = _first_family(value)
            if family:
                parsed.tallies["fonts"][_clip("@font-face " + family)] += 1
        return
    plain = _STRING_RE.sub('""', value)
    if name.startswith("--"):
        parsed.custom.setdefault(_clip(name), _clip(value))
        colors = extract_colors(plain, False)
        whole = _whole_color_value(plain)
        if whole and not colors:
            colors = [whole]
        for color in colors:
            parsed.tallies["colors"][color] += 1
        return
    name = _VENDOR_PREFIX_RE.sub("", name.lower())
    allow_named = name in _NAMED_COLOR_PROPS or name.startswith(_NAMED_COLOR_PREFIXES)
    for color in extract_colors(plain, allow_named):
        parsed.tallies["colors"][color] += 1
    lowered = " ".join(value.lower().split())
    if name == "font-family":
        family = _first_family(value)
        if family:
            parsed.tallies["fonts"][_clip(family)] += 1
    elif name == "font":
        font = _parse_font_shorthand(value)
        if font is not None:
            size, family = font
            if not _is_noise_value(size):
                parsed.tallies["font_sizes"][_clip(size)] += 1
            if family:
                parsed.tallies["fonts"][_clip(family)] += 1
    elif name == "font-size":
        if not _is_noise_value(lowered):
            parsed.tallies["font_sizes"][_clip(lowered)] += 1
    elif _RADIUS_RE.match(name):
        if not _is_noise_value(lowered):
            parsed.tallies["radii"][_clip(lowered)] += 1
    elif name == "box-shadow":
        if not _is_noise_value(lowered):
            parsed.tallies["shadows"][_clip(lowered)] += 1
    elif _SPACING_RE.match(name):
        for token in _split_tokens(lowered):
            if token in _IGNORED_KEYWORDS or token in ("auto", "0", "0px") or token.startswith("var("):
                continue
            parsed.tallies["spacing"][_clip(token)] += 1


def _declarations(parsed: _Parsed, body: str, in_font_face: bool) -> None:
    for chunk in body.split(";"):
        name, sep, value = chunk.partition(":")
        if sep:
            _declaration(parsed, name, value, in_font_face)


def _classify(prelude: str, parent: str) -> str:
    if parent == "skip":
        return "skip"
    prelude = prelude.strip().lower()
    if prelude.startswith("@"):
        if "keyframes" in prelude:
            return "skip"
        if prelude.startswith("@font-face"):
            return "fontface"
        return "group" if prelude.startswith(_GROUP_AT_RULES) else "skip"
    return "rule"


def _string_end(text: str, start: int) -> Tuple[int, bool]:
    """Index just past the string opened at `start`, and whether its closing quote was found.

    A string ends at its quote, or unclosed at the first newline or end of input.
    """
    ender = _STRING_END_RES[text[start]]
    pos = start + 1
    while True:
        match = ender.search(text, pos)
        if match is None:
            return len(text), False
        found = match.group()
        if found == "\\":
            pos = match.end() + 1
        elif found == "\n":
            return match.start(), False
        else:
            return match.end(), True


def _scrub(text: str) -> str:
    """Drop comments, reduce url(...) to url() and blank strings holding `{`, `}` or `;`.

    One pass: every step moves the position forward, so cost is linear in len(text).
    An unclosed comment drops the rest; an unclosed url( ends at the next `)` or end of input.
    """
    out: List[str] = []
    pos = 0
    length = len(text)
    while pos < length:
        match = _SCAN_RE.search(text, pos)
        if match is None:
            out.append(text[pos:])
            break
        start = match.start()
        out.append(text[pos:start])
        token = match.group()
        if token == "/*":
            end = text.find("*/", start + 2)
            if end < 0:
                break
            pos = end + 2
        elif token == "\\":
            out.append(text[start:start + 2])
            pos = start + 2
        elif token in ('"', "'"):
            end, closed = _string_end(text, start)
            body = text[start:end]
            out.append(body if closed and _SYNTAX_RE.search(body) is None else '""')
            pos = end
        else:
            pos = match.end()
            pos = _SPACE_RE.match(text, pos).end()
            if pos < length and text[pos] in "\"'":
                pos = _string_end(text, pos)[0]
            while True:
                end = _URL_END_RE.search(text, pos)
                if end is None:
                    pos = length
                    break
                if end.group() == ")":
                    pos = end.end()
                    break
                pos = end.end() + 1
            out.append("url()")
    return "".join(out)


def parse_css(text: str) -> _Parsed:
    parsed = _Parsed()
    text = _scrub(text)
    stack: List[str] = []
    last = 0
    for match in _BRACE_RE.finditer(text):
        pos = match.start()
        chunk = text[last:pos]
        last = pos + 1
        top = stack[-1] if stack else "group"
        if match.group() == "{":
            decls, _, prelude = chunk.rpartition(";")
            if top in ("rule", "fontface") and decls:
                _declarations(parsed, decls, top == "fontface")
            stack.append(_classify(prelude, top))
        else:
            if stack:
                if top in ("rule", "fontface"):
                    _declarations(parsed, chunk, top == "fontface")
                stack.pop()
    return parsed


# ---- source resolution ------------------------------------------------------------


def _read_text(path: Path, limit: int) -> Tuple[str, bool]:
    with open(path, "rb") as handle:
        data = handle.read(limit + 1)
    truncated = len(data) > limit
    return data[:limit].decode("utf-8", errors="replace"), truncated


def _is_remote(href: str) -> bool:
    lowered = href.lower()
    return lowered.startswith(("http:", "https:", "//"))


def _resolve_local(source_real: str, page: Path, href: str) -> Optional[Path]:
    """The regular file `href` names relative to `page`, only if it stays inside the source."""
    cleaned = unquote(re.split(r"[?#]", href, maxsplit=1)[0].strip())
    if not cleaned or "\x00" in cleaned or cleaned.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", cleaned):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", cleaned):
        return None
    candidate = os.path.realpath(os.path.join(str(page.parent), cleaned))
    try:
        inside = os.path.commonpath([source_real, candidate]) == source_real
    except ValueError:
        return None
    if not inside or candidate == source_real or not os.path.isfile(candidate):
        return None
    return Path(candidate)


class _Raw:
    def __init__(self) -> None:
        self.pages: List[str] = []
        self.count: Dict[str, Counter] = {c: Counter() for c in CATEGORIES}
        self.page_count: Dict[str, Counter] = {c: Counter() for c in CATEGORIES}
        self.custom: Dict[str, str] = {}
        self.truncated_css: Set[str] = set()
        self.skipped_css: Set[str] = set()
        self.remote = 0
        self.fonts: List[str] = []
        self.images: List[str] = []


def _list_assets(source_dir: Path, raw: _Raw) -> None:
    for current, dirnames, filenames in os.walk(source_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__MACOSX"
                       and not os.path.islink(os.path.join(current, d))]
        for filename in filenames:
            path = Path(current) / filename
            if filename.startswith(".") or path.is_symlink():
                continue
            lowered = filename.lower()
            rel = _clip_path(_clean_text(path.relative_to(source_dir).as_posix()))
            if lowered.endswith(FONT_EXTS):
                raw.fonts.append(rel)
            elif lowered.endswith(IMAGE_EXTS):
                raw.images.append(rel)
    raw.fonts.sort()
    raw.images.sort()


def _collect(source_dir: Path) -> _Raw:
    source_dir = Path(source_dir)
    try:
        pages = find_pages(source_dir)
    except UnpackError as exc:
        raise EvidenceError(str(exc)) from exc
    if not pages:
        raise EvidenceError("no html pages found in %s" % source_dir.name)
    source_real = os.path.realpath(str(source_dir))
    raw = _Raw()
    sheet_cache: Dict[str, _Parsed] = {}

    for page in pages:
        raw.pages.append(_clip_path(_clean_text(page.relative_to(source_dir).as_posix())))
        html_text, page_truncated = _read_text(page, MAX_PAGE_BYTES)
        if page_truncated:
            raise EvidenceError("page larger than %d bytes: %s" % (MAX_PAGE_BYTES, raw.pages[-1]))
        doc = html_tree.parse(html_text)
        sources: List[_Parsed] = []
        seen_files: Set[str] = set()
        nodes = list(html_tree.iter_elements(doc.head)) + list(html_tree.iter_elements(doc.body.children))
        for element in nodes:
            if element.tag == "style":
                sources.append(parse_css("".join(c for c in element.children if isinstance(c, str))))
            elif element.tag == "link":
                rels = (element.get("rel") or "").lower().split()
                href = (element.get("href") or "").strip()
                if "stylesheet" not in rels or not href:
                    continue
                if _is_remote(href):
                    raw.remote += 1
                    continue
                resolved = _resolve_local(source_real, page, href)
                if resolved is None:
                    raw.skipped_css.add(_clip_path(_clean_text(href)))
                    continue
                key = str(resolved)
                if key in seen_files:
                    continue
                seen_files.add(key)
                if key not in sheet_cache:
                    css, truncated = _read_text(resolved, MAX_CSS_BYTES)
                    if truncated:
                        raw.truncated_css.add(_clip_path(_clean_text(os.path.relpath(key, source_real).replace(os.sep, "/"))))
                    sheet_cache[key] = parse_css(css)
                sources.append(sheet_cache[key])
        page_tally: Dict[str, Counter] = {c: Counter() for c in CATEGORIES}
        for parsed in sources:
            for category in CATEGORIES:
                page_tally[category].update(parsed.tallies[category])
            for name, value in parsed.custom.items():
                raw.custom.setdefault(name, value)
        for category in CATEGORIES:
            raw.count[category].update(page_tally[category])
            raw.page_count[category].update(page_tally[category].keys())
    _list_assets(source_dir, raw)
    return raw


# ---- output -----------------------------------------------------------------------


def _custom_group(value: str) -> int:
    """Relevance for the custom-property cap: 0 single color, 1 single length, 2 the rest."""
    if _whole_color(value) is not None:
        return 0
    return 1 if _LENGTH_RE.match(value.strip().lower()) else 2


def _render(raw: _Raw, top_n: int) -> dict:
    if top_n < 1:
        raise EvidenceError("top_n must be at least 1")
    list_cap = min(200, top_n * 8)
    asset_cap = min(100, top_n * 4)
    out: dict = {}
    out["pages"] = [_clip_path(_clean_text(p)) for p in raw.pages[:list_cap]]
    out["pages_total"] = len(raw.pages)
    for category in CATEGORIES:
        ordered = sorted(raw.count[category].items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        out[category] = [
            {"value": _clip(_clean_text(value)), "count": count, "pages": raw.page_count[category][value]}
            for value, count in ordered
        ]
    names = sorted(raw.custom, key=lambda n: (_custom_group(raw.custom[n]), n))
    chosen = sorted(names[:list_cap])
    out["custom_properties"] = {_clip(_clean_text(n)): _clip(_clean_text(raw.custom[n])) for n in chosen}
    out["custom_properties_total"] = len(names)
    out["assets"] = {
        "fonts": [_clip_path(_clean_text(f)) for f in raw.fonts[:asset_cap]],
        "images": [_clip_path(_clean_text(f)) for f in raw.images[:asset_cap]],
    }
    out["assets_truncated"] = {
        "fonts": max(0, len(raw.fonts) - asset_cap),
        "images": max(0, len(raw.images) - asset_cap),
    }
    out["truncated_css"] = [_clip_path(_clean_text(p)) for p in sorted(raw.truncated_css)[:list_cap]]
    out["skipped_css"] = [_clip_path(_clean_text(p)) for p in sorted(raw.skipped_css)[:list_cap]]
    out["remote_stylesheets"] = raw.remote
    return out


def gather_evidence(source_dir: Path, top_n: int = DEFAULT_TOP_N) -> dict:
    return _render(_collect(Path(source_dir)), top_n)


def _dump(evidence: dict) -> str:
    return json.dumps(evidence, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_evidence(source_dir: Path, out: Path, top_n: int = DEFAULT_TOP_N) -> None:
    raw = _collect(Path(source_dir))
    while True:
        text = _dump(_render(raw, top_n))
        size = len(text.encode("utf-8"))
        if size <= MAX_JSON_BYTES:
            break
        if top_n <= MIN_TOP_N:
            raise EvidenceError("evidence is %d bytes, over the %d byte limit even at top_n=%d"
                                % (size, MAX_JSON_BYTES, top_n))
        top_n = max(MIN_TOP_N, top_n // 2)
    Path(out).write_bytes(text.encode("utf-8"))


def main(argv: List[str]) -> int:
    args = list(argv)
    top_n = DEFAULT_TOP_N
    if "--top-n" in args:
        i = args.index("--top-n")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        try:
            top_n = int(args[i + 1])
        except ValueError:
            print(USAGE, file=sys.stderr)
            return 2
        if top_n < 1:
            print(USAGE, file=sys.stderr)
            return 2
        args = args[:i] + args[i + 2:]
    if len(args) != 2 or any(a.startswith("--") for a in args):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        write_evidence(Path(args[0]), Path(args[1]), top_n)
    except (EvidenceError, OSError) as exc:
        print("error: %s" % str(exc).replace("\n", " "), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
