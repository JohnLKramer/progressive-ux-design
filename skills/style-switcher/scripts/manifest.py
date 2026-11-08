from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

from problems import Problem  # noqa: E402

MANIFEST_NAME = "manifest.json"


def slugify(title: str, taken: Set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "page"
    candidate = base
    n = 2
    while candidate in taken:
        candidate = "%s-%d" % (base, n)
        n += 1
    return candidate


def style_display_name(style_dir: Path) -> str:
    name_file = style_dir / "name.txt"
    if name_file.is_file():
        name = name_file.read_text(encoding="utf-8").strip()
        if name:
            return name
    return style_dir.name


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.done = False
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "title" and not self.done:
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.in_title:
            self.in_title = False
            self.done = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)


def _page_title(page_dir: Path) -> str:
    index = page_dir / "index.html"
    if index.is_file():
        parser = _TitleParser()
        parser.feed(index.read_text(encoding="utf-8"))
        parser.close()
        title = " ".join("".join(parser.parts).split())
        if title:
            return title
    return page_dir.name


def _subdirs(parent: Path) -> List[Path]:
    if not parent.is_dir():
        return []
    return sorted((p for p in parent.iterdir() if p.is_dir()), key=lambda p: p.name)


def build_manifest(workspace: Path) -> dict:
    workspace = Path(workspace)
    return {
        "pages": [{"slug": d.name, "title": _page_title(d)} for d in _subdirs(workspace / "pages")],
        "styles": [
            {"id": d.name, "name": style_display_name(d), "hasLayout": (d / "layout.css").is_file()}
            for d in _subdirs(workspace / "styles")
        ],
    }


def write_manifest(workspace: Path) -> Path:
    workspace = Path(workspace)
    path = workspace / MANIFEST_NAME
    text = json.dumps(build_manifest(workspace), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_bytes(text.encode("utf-8"))
    return path


def _entries(manifest: dict, key: str, fields: dict, problems: List[Problem]) -> List[dict]:
    """Return well-formed entries of manifest[key]; report the rest as malformed."""
    value = manifest.get(key)
    if not isinstance(value, list):
        problems.append(Problem("malformed", key, "'%s' must be a list" % key))
        return []
    good = []
    for i, entry in enumerate(value):
        where = "%s[%d]" % (key, i)
        if not isinstance(entry, dict):
            problems.append(Problem("malformed", where, "entry must be an object"))
            continue
        ok = True
        for field, typ in fields.items():
            if not isinstance(entry.get(field), typ):
                problems.append(Problem("malformed", where, "'%s' must be %s" % (field, typ.__name__)))
                ok = False
        if ok:
            good.append(entry)
    return good


def _check_file(path: Path, where: str, problems: List[Problem]) -> None:
    if not path.is_file():
        problems.append(Problem("missing-file", where, "%s does not exist" % path))


def validate_manifest(workspace: Path) -> List[Problem]:
    workspace = Path(workspace)
    if not workspace.is_dir():
        raise FileNotFoundError("workspace directory not found: %s" % workspace)
    path = workspace / MANIFEST_NAME
    if not path.is_file():
        return [Problem("malformed", MANIFEST_NAME, "manifest file is missing")]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [Problem("malformed", MANIFEST_NAME, "not valid JSON: %s" % exc)]
    if not isinstance(manifest, dict):
        return [Problem("malformed", MANIFEST_NAME, "top level must be an object")]

    problems: List[Problem] = []
    pages = _entries(manifest, "pages", {"slug": str, "title": str}, problems)
    styles = _entries(manifest, "styles", {"id": str, "name": str, "hasLayout": bool}, problems)

    if isinstance(manifest.get("pages"), list) and not manifest["pages"]:
        problems.append(Problem("empty", "pages", "workspace has no pages"))
    if isinstance(manifest.get("styles"), list) and not manifest["styles"]:
        problems.append(Problem("empty", "styles", "workspace has no styles"))

    seen_slugs: Set[str] = set()
    for page in pages:
        slug = page["slug"]
        if slug in seen_slugs:
            problems.append(Problem("malformed", "pages/%s" % slug, "duplicate page slug"))
        seen_slugs.add(slug)
        _check_file(workspace / "pages" / slug / "index.html", "pages/%s" % slug, problems)

    seen_ids: Set[str] = set()
    for style in styles:
        style_id = style["id"]
        where = "styles/%s" % style_id
        if style_id in seen_ids:
            problems.append(Problem("duplicate-style-id", where, "duplicate style id"))
        seen_ids.add(style_id)
        style_dir = workspace / "styles" / style_id
        _check_file(style_dir / "style.css", where, problems)
        _check_file(style_dir / "tokens.json", where, problems)
        if style["hasLayout"]:
            _check_file(style_dir / "layout.css", where, problems)
    return problems


USAGE = "usage: manifest.py slug <text> [--taken a,b,c]"


def main(argv: List[str]) -> int:
    if len(argv) < 2 or argv[0] != "slug":
        print(USAGE, file=sys.stderr)
        return 2
    rest = argv[1:]
    taken: Set[str] = set()
    if "--taken" in rest:
        i = rest.index("--taken")
        if i + 1 >= len(rest):
            print(USAGE, file=sys.stderr)
            return 2
        taken = {t for t in rest[i + 1].split(",") if t}
        rest = rest[:i] + rest[i + 2:]
    if len(rest) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    print(slugify(rest[0], taken))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
