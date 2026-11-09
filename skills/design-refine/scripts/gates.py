"""Gates for the design-refine loop.

Marker diff: the (attr, value) markers in a page are its structural contract. Moving
elements or adding wrappers is fine; any change to the multiset of markers is reported.
A missing or unreadable file raises; it is never treated as "no markers".

Snapshot, check, restore: before a fix, `snapshot` copies the roots the fixer may touch
(the page, the primary style, the cross style, the doc) and hashes every workspace file.
`check` reports what the fix broke or touched out of scope. `restore` puts the roots
back. It only ever deletes or replaces recorded roots, and refuses a snapshot whose
roots do not match what `snapshot` would have recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


# --- snapshot / check / restore -----------------------------------------

WORK_DIR = ".design-refine"
SNAPSHOT_FILE = "snapshot.json"
SNAPSHOT_VERSION = 1
_EXTERNAL_DOC_DIR = "_external_doc"


def _check_name(kind: str, name: str) -> None:
    """A slug or style id must be one plain path component."""
    if not isinstance(name, str) or name in ("", ".", "..") or "/" in name or "\\" in name:
        raise ValueError("%s must be a single path component, got %r" % (kind, name))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_workspace(workspace: Path) -> Dict[str, str]:
    """sha256 of every file under workspace, keyed by posix relative path, skipping WORK_DIR."""
    hashes = {}  # type: Dict[str, str]
    for dirpath, dirnames, filenames in os.walk(str(workspace)):
        here = Path(dirpath)
        if here == workspace:
            dirnames[:] = [d for d in dirnames if d != WORK_DIR]
        dirnames.sort()
        for name in sorted(filenames):
            path = here / name
            hashes[path.relative_to(workspace).as_posix()] = _hash_file(path)
    return hashes


def _expected_roots(workspace: Path, slug: str, style_id: str, cross_style: Optional[str], doc: Optional[str]):
    """The (path, kind, copy) roots for these inputs. snapshot records them; restore re-derives them."""
    roots = [
        (workspace / "pages" / slug, "dir"),
        (workspace / "styles" / style_id, "dir"),
    ]
    if cross_style is not None:
        roots.append((workspace / "styles" / cross_style, "dir"))
    if doc is not None:
        roots.append((Path(doc), "file"))
    out = []
    for path, kind in roots:
        if _is_within(path, workspace):
            copy = "roots/" + path.relative_to(workspace).as_posix()
        else:
            copy = "roots/%s/%s" % (_EXTERNAL_DOC_DIR, path.name)
        out.append({"path": str(path), "kind": kind, "copy": copy})
    return out


def snapshot(
    workspace: Path,
    slug: str,
    style_id: str,
    dest: Path,
    cross_style: Optional[str] = None,
    doc: Optional[Path] = None,
) -> dict:
    """Copy the roots into dest/roots/ and write dest/snapshot.json. Returns the recorded data."""
    _check_name("slug", slug)
    _check_name("style_id", style_id)
    if cross_style is not None:
        _check_name("cross_style", cross_style)
        if cross_style == style_id:
            raise ValueError("cross_style %r is the primary style" % cross_style)

    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise FileNotFoundError("workspace %s is not a directory" % workspace)
    page = workspace / "pages" / slug / "index.html"
    if not page.is_file():
        raise FileNotFoundError("page %s does not exist" % page)
    for sid in [style_id] + ([cross_style] if cross_style is not None else []):
        style_dir = workspace / "styles" / sid
        if not style_dir.is_dir():
            raise FileNotFoundError("style %s does not exist" % style_dir)
    doc_str = None  # type: Optional[str]
    if doc is not None:
        doc_path = Path(doc).resolve()
        if not doc_path.is_file():
            raise FileNotFoundError("doc %s does not exist" % doc_path)
        if _is_within(doc_path, workspace / WORK_DIR):
            raise ValueError("doc %s is inside %s" % (doc_path, WORK_DIR))
        doc_str = str(doc_path)

    roots = _expected_roots(workspace, slug, style_id, cross_style, doc_str)

    dest = Path(dest).resolve()
    if _is_within(dest, workspace) and not _is_within(dest, workspace / WORK_DIR):
        raise ValueError("snapshot dest %s is inside the workspace but not under %s" % (dest, WORK_DIR))
    for root in roots:
        if _is_within(dest, Path(root["path"])):
            raise ValueError("snapshot dest %s is inside root %s" % (dest, root["path"]))
    if dest.exists():
        if not dest.is_dir():
            raise FileExistsError("snapshot dest %s exists and is not a directory" % dest)
        if any(dest.iterdir()):
            raise FileExistsError("snapshot dest %s exists and is not empty" % dest)

    hashes = _hash_workspace(workspace)
    dest.mkdir(parents=True, exist_ok=True)
    for root in roots:
        src, copy = Path(root["path"]), dest / root["copy"]
        if root["kind"] == "dir":
            shutil.copytree(str(src), str(copy), symlinks=True)
        else:
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(copy))

    data = {
        "version": SNAPSHOT_VERSION,
        "workspace": str(workspace),
        "slug": slug,
        "style_id": style_id,
        "cross_style": cross_style,
        "doc": doc_str,
        "doc_sha256": _hash_file(Path(doc_str)) if doc_str is not None else None,
        "roots": roots,
        "hashes": hashes,
    }
    (dest / SNAPSHOT_FILE).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data
