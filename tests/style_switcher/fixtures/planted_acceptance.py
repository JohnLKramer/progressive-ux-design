from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from finalize_style import lint_style
from validate_style import _COMMENT, _URL_FN, find_remote_urls, validate_style
from vocab import WRAPPERS, load_roles

PLANTED_COLORS = ("#7a1fa2", "#ffb300", "#00897b", "#f4f1ea")
PLANTED_FAMILY = "Planted Sans"
PLANTED_FONT_FILE = "assets/planted-sans.woff2"
_FONT_FACE = re.compile(r"@font-face\s*\{([^}]*)\}", re.IGNORECASE)
_FAMILY = re.compile(r"(?:^|;)\s*font-family\s*:\s*([\"']?)%s\1\s*(?=;|$)" % re.escape(PLANTED_FAMILY), re.IGNORECASE)
_SRC = re.compile(r"(?:^|;)\s*src\s*:([^;]*)", re.IGNORECASE)


def _strings(value) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


def _role_pattern(role: str) -> "re.Pattern[str]":
    quoted = re.escape(role)
    return re.compile(r"""\[\s*data-sp\s*=\s*(?:"%s"|'%s'|%s)\s*\]""" % (quoted, quoted, quoted))


def _selectors(css: str) -> List[str]:
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.DOTALL)
    return [chunk.rsplit("}", 1)[-1] for chunk in css.split("{")[:-1]]


def _font_failures(style_dir: Path, css_path: Path) -> List[str]:
    failures: List[str] = []
    css = _COMMENT.sub(" ", css_path.read_text(encoding="utf-8")) if css_path.is_file() else ""
    declared = False
    for body in _FONT_FACE.findall(css):
        body = body.strip()
        if not _FAMILY.search(body):
            continue
        for src in _SRC.findall(body):
            for match in _URL_FN.finditer(src):
                ref = next(g for g in match.groups() if g is not None).strip()
                while ref.startswith("./"):
                    ref = ref[2:]
                declared = declared or ref == PLANTED_FONT_FILE
    if not declared:
        failures.append("style.css has no @font-face for %s whose src is %s" % (PLANTED_FAMILY, PLANTED_FONT_FILE))
    if not (style_dir / PLANTED_FONT_FILE).is_file():
        failures.append("%s is missing from the style directory" % PLANTED_FONT_FILE)
    return failures


def check_planted_style(style_dir: Path) -> List[str]:
    style_dir = Path(style_dir)
    failures: List[str] = ["validate_style: %s: %s: %s" % (p.code, p.where, p.message)
                           for p in validate_style(style_dir)]

    tokens = {}
    tokens_path = style_dir / "tokens.json"
    if tokens_path.is_file():
        try:
            tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            tokens = {}
    if not isinstance(tokens, dict):
        tokens = {}

    palette = {s.strip().lower() for s in _strings(tokens.get("palette"))}
    for color in PLANTED_COLORS:
        if color not in palette:
            failures.append("palette is missing planted color %s" % color)

    if not any(PLANTED_FAMILY in s for s in _strings(tokens.get("fonts"))):
        failures.append("fonts do not name %s" % PLANTED_FAMILY)

    css_path = style_dir / "style.css"
    selectors = _selectors(css_path.read_text(encoding="utf-8")) if css_path.is_file() else []
    for role in sorted(load_roles() | set(WRAPPERS)):
        pattern = _role_pattern(role)
        if not any(pattern.search(sel) for sel in selectors):
            failures.append("style.css has no rule for [data-sp=\"%s\"]" % role)

    for name in ("style.css", "layout.css"):
        path = style_dir / name
        if path.is_file():
            for url in find_remote_urls(path.read_text(encoding="utf-8")):
                failures.append("%s has a remote URL: %s" % (name, url))

    failures.extend(_font_failures(style_dir, css_path))
    for name in ("name.txt", "notes.md"):
        path = style_dir / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            failures.append("%s is missing or empty" % name)
    failures.extend("lint_style: %s: %s: %s" % (p.code, p.where, p.message) for p in lint_style(style_dir))
    return failures
