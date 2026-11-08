from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from problems import Problem

REQUIRED_TOKEN_KEYS = ("palette", "fonts", "scale", "spacing", "radii", "shadows")

_COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)", re.DOTALL)
_URL_FN = re.compile(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)\"']*))\s*\)", re.IGNORECASE)
_IMPORT_STR = re.compile(r"@import\s+(?:\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)
_DECL = re.compile(r"^\s*([a-zA-Z-]+)\s*:\s*(.*?)\s*$", re.DOTALL)
_IMPORTANT = re.compile(r"\s*!\s*important\s*$", re.IGNORECASE)
_REMOTE_PREFIXES = ("http:", "https:", "//")

_REORDER_PROPS = (
    "order",
    "grid-area",
    "grid-row",
    "grid-row-start",
    "grid-row-end",
    "grid-column",
    "grid-column-start",
    "grid-column-end",
    "grid-template",
    "grid-template-areas",
)


def _strip_comments(css: str) -> str:
    return _COMMENT.sub(" ", css)


def find_remote_urls(css: str) -> List[str]:
    css = _strip_comments(css)
    found: List[str] = []
    for pattern in (_URL_FN, _IMPORT_STR):
        for match in pattern.finditer(css):
            value = next(g for g in match.groups() if g is not None).strip()
            if value.lower().startswith(_REMOTE_PREFIXES):
                found.append(value)
    return found


def find_forbidden_layout_rules(css: str) -> List[Problem]:
    problems: List[Problem] = []
    for chunk in re.split(r"[{};]", _strip_comments(css)):
        match = _DECL.match(chunk)
        if not match:
            continue
        prop = match.group(1).lower()
        value = _IMPORTANT.sub("", match.group(2)).strip().lower()
        decl = "%s: %s" % (prop, value)
        if prop == "display" and value == "none":
            problems.append(Problem("layout-hides", "layout.css", "forbidden `%s`" % decl))
        elif prop == "visibility" and value == "hidden":
            problems.append(Problem("layout-hides", "layout.css", "forbidden `%s`" % decl))
        elif prop in _REORDER_PROPS:
            problems.append(Problem("layout-reorders", "layout.css", "forbidden `%s`" % decl))
        elif prop == "flex-direction" and value.endswith("-reverse"):
            problems.append(Problem("layout-reorders", "layout.css", "forbidden `%s`" % decl))
        elif prop == "flex-flow" and "reverse" in value:
            problems.append(Problem("layout-reorders", "layout.css", "forbidden `%s`" % decl))
    return problems


def _check_tokens(path: Path) -> List[Problem]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Problem("bad-tokens", str(path), "invalid JSON: %s" % exc)]
    if not isinstance(data, dict):
        return [Problem("bad-tokens", str(path), "tokens.json must be an object")]
    missing = [key for key in REQUIRED_TOKEN_KEYS if key not in data]
    if missing:
        return [Problem("bad-tokens", str(path), "missing keys: %s" % ", ".join(missing))]
    return []


def validate_style(style_dir: Path) -> List[Problem]:
    style_dir = Path(style_dir)
    problems: List[Problem] = []

    for name in ("style.css", "tokens.json"):
        if not (style_dir / name).is_file():
            problems.append(Problem("missing-file", str(style_dir / name), "required file is missing"))

    tokens = style_dir / "tokens.json"
    if tokens.is_file():
        problems.extend(_check_tokens(tokens))

    for name in ("style.css", "layout.css"):
        path = style_dir / name
        if path.is_file():
            for url in find_remote_urls(path.read_text(encoding="utf-8")):
                problems.append(Problem("remote-url", str(path), "remote URL: %s" % url))

    layout = style_dir / "layout.css"
    if layout.is_file():
        for problem in find_forbidden_layout_rules(layout.read_text(encoding="utf-8")):
            problems.append(Problem(problem.code, str(layout), problem.message))

    return problems
