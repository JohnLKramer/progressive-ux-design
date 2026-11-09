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

import argparse
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

from problems import Problem, format_problems  # noqa: E402
from validate_page import collect_data_el, validate_page  # noqa: E402
from validate_style import validate_style  # noqa: E402

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


class SnapshotError(ValueError):
    """A snapshot is malformed, or its roots do not lie where this module requires."""


def _check_roots_contained(workspace: Path, roots: List[dict], doc: Optional[str], context: str) -> None:
    """Every root must resolve (symlinks followed) strictly inside the workspace and outside
    WORK_DIR. The one exception is the recorded doc file, which may live anywhere."""
    real_ws = workspace.resolve()
    work_dir = real_ws / WORK_DIR
    for root in roots:
        resolved = Path(root["path"]).resolve()
        if root["kind"] == "file" and root["path"] == doc and resolved == Path(doc):
            continue
        if resolved == real_ws or not _is_within(resolved, real_ws) or _is_within(resolved, work_dir):
            raise SnapshotError(
                "%s: root %s resolves to %s, outside the workspace" % (context, root["path"], resolved)
            )


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
    # Checked before dest is touched: a root symlinked out of the workspace would make every
    # later check and restore refuse, so the iteration could not be reverted.
    _check_roots_contained(workspace, roots, doc_str, "snapshot of %s" % workspace)

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


_KINDS = ("structural", "style")


def _load_snapshot(snapshot_dir: Path) -> dict:
    """Read and validate snapshot.json. Raises FileNotFoundError or SnapshotError; never guesses."""
    path = Path(snapshot_dir) / SNAPSHOT_FILE
    if not path.is_file():
        raise FileNotFoundError("snapshot file %s does not exist" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotError("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(data, dict):
        raise SnapshotError("%s must hold an object" % path)
    if data.get("version") != SNAPSHOT_VERSION:
        raise SnapshotError("%s has version %r, expected %d" % (path, data.get("version"), SNAPSHOT_VERSION))
    try:
        workspace_str = data["workspace"]
        slug, style_id = data["slug"], data["style_id"]
        cross_style, doc = data["cross_style"], data["doc"]
        roots, hashes, doc_sha = data["roots"], data["hashes"], data["doc_sha256"]
    except KeyError as exc:
        raise SnapshotError("%s is missing key %s" % (path, exc))
    try:
        _check_name("slug", slug)
        _check_name("style_id", style_id)
        if cross_style is not None:
            _check_name("cross_style", cross_style)
    except ValueError as exc:
        raise SnapshotError("%s: %s" % (path, exc))
    if not isinstance(workspace_str, str) or not Path(workspace_str).is_absolute():
        raise SnapshotError("%s: workspace must be an absolute path, got %r" % (path, workspace_str))
    workspace = Path(workspace_str)
    if not workspace.is_dir():
        raise SnapshotError("%s: workspace %s is not a directory" % (path, workspace))
    if doc is not None and (not isinstance(doc, str) or not Path(doc).is_absolute()):
        raise SnapshotError("%s: doc must be null or an absolute path, got %r" % (path, doc))
    if (doc is None) != (doc_sha is None):
        raise SnapshotError("%s: doc and doc_sha256 must both be set or both be null" % path)
    if not isinstance(hashes, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in hashes.items()
    ):
        raise SnapshotError("%s: hashes must map paths to sha256 strings" % path)
    expected = _expected_roots(workspace, slug, style_id, cross_style, doc)
    if roots != expected:
        raise SnapshotError("%s: roots %r do not match the expected roots %r" % (path, roots, expected))
    # Symlinks could point a root elsewhere since the snapshot was taken.
    _check_roots_contained(workspace, roots, doc, str(path))
    return data


def _rel_in_scope(rel: str, kind: str, data: dict, workspace: Path) -> bool:
    if kind == "structural":
        if rel.startswith("pages/%s/" % data["slug"]):
            return True
        doc = data["doc"]
        if doc is None or not _is_within(Path(doc), workspace):
            return False
        return Path(doc).relative_to(workspace).as_posix() == rel
    return rel.startswith("styles/%s/" % data["style_id"])


def _rel_in_roots(rel: str, data: dict, workspace: Path) -> bool:
    for root in data["roots"]:
        path = Path(root["path"])
        if not _is_within(path, workspace):
            continue
        root_rel = path.relative_to(workspace).as_posix()
        if rel == root_rel or (root["kind"] == "dir" and rel.startswith(root_rel + "/")):
            return True
    return False


def _out_of_scope(where: str, what: str, kind: str, revertable: bool) -> Problem:
    tail = (
        "restore will revert it"
        if revertable
        else "it lies outside the snapshot roots and cannot be auto-reverted"
    )
    return Problem("file-out-of-scope", where, "%s, outside the files a %s fix may touch; %s" % (what, kind, tail))


def check(snapshot_dir: Path, kind: str) -> List[Problem]:
    """Gate a fix: allowed files, marker diff, page validator, style validator, in that order."""
    if kind not in _KINDS:
        raise ValueError("kind must be one of %s, got %r" % (", ".join(_KINDS), kind))
    snapshot_dir = Path(snapshot_dir)
    data = _load_snapshot(snapshot_dir)
    workspace = Path(data["workspace"])
    problems = []  # type: List[Problem]

    before, after = data["hashes"], _hash_workspace(workspace)
    for rel in sorted(set(before) | set(after)):
        if before.get(rel) == after.get(rel) or _rel_in_scope(rel, kind, data, workspace):
            continue
        what = "added" if rel not in before else "removed" if rel not in after else "changed"
        problems.append(_out_of_scope(rel, what, kind, _rel_in_roots(rel, data, workspace)))

    doc = data["doc"]
    if doc is not None and not _is_within(Path(doc), workspace) and kind != "structural":
        doc_path = Path(doc)
        current = _hash_file(doc_path) if doc_path.is_file() else None
        if current != data["doc_sha256"]:
            problems.append(_out_of_scope(doc, "removed" if current is None else "changed", kind, True))

    page = workspace / "pages" / data["slug"] / "index.html"
    page_before = snapshot_dir / "roots" / "pages" / data["slug"] / "index.html"
    if page.is_file():
        problems.extend(marker_diff(page_before, page))
        problems.extend(validate_page(page, source_el_ids=collect_data_el(page_before)))
    else:
        problems.append(Problem("page-missing", str(page), "the page was deleted"))

    problems.extend(validate_style(workspace / "styles" / data["style_id"]))
    return problems


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))
    elif os.path.lexists(str(path)):
        raise OSError("cannot remove %s: not a file, directory or symlink" % path)


def restore(snapshot_dir: Path) -> None:
    """Replace every recorded root with its snapshot copy. Touches nothing else.

    Everything is validated before the first deletion: a bad snapshot.json, a root that
    resolves outside the workspace, or a missing copy raises with the workspace unchanged.
    """
    snapshot_dir = Path(snapshot_dir).resolve()
    data = _load_snapshot(snapshot_dir)
    roots_dir = snapshot_dir / "roots"
    plan = []  # type: List[Tuple[Path, Path, str]]
    for root in data["roots"]:
        copy = (snapshot_dir / root["copy"]).resolve()
        if not _is_within(copy, roots_dir):
            raise SnapshotError("copy %s for root %s is outside %s" % (copy, root["path"], roots_dir))
        if root["kind"] == "dir" and not copy.is_dir():
            raise FileNotFoundError("snapshot copy %s of root %s is missing" % (copy, root["path"]))
        if root["kind"] == "file" and not copy.is_file():
            raise FileNotFoundError("snapshot copy %s of root %s is missing" % (copy, root["path"]))
        target = Path(root["path"])
        tmp = target.with_name("." + target.name + ".restore-tmp")
        if os.path.lexists(str(tmp)):
            raise FileExistsError("restore scratch path %s already exists; remove it by hand" % tmp)
        plan.append((copy, target, root["kind"]))

    for copy, target, kind in plan:
        # Copy beside the target first, so a failed copy leaves the target as it was.
        tmp = target.with_name("." + target.name + ".restore-tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "dir":
            shutil.copytree(str(copy), str(tmp), symlinks=True)
        else:
            shutil.copy2(str(copy), str(tmp))
        _remove(target)
        os.replace(str(tmp), str(target))


# --- CLI -----------------------------------------------------------------


def _default_cross_style(workspace: Path, style_id: str) -> Optional[str]:
    """The first style id, in sorted order, other than style_id that has a layout.css."""
    styles = Path(workspace) / "styles"
    if not styles.is_dir():
        return None
    for entry in sorted(styles.iterdir(), key=lambda p: p.name):
        if entry.name != style_id and entry.is_dir() and (entry / "layout.css").is_file():
            return entry.name
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gates.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("snapshot")
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--style", required=True)
    p.add_argument("--cross-style")
    p.add_argument("--doc", type=Path)
    p.add_argument("--dest", type=Path, required=True)
    p = sub.add_parser("check")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--kind", choices=_KINDS, required=True)
    p = sub.add_parser("restore")
    p.add_argument("--snapshot", type=Path, required=True)
    return parser


def _dispatch(args: argparse.Namespace) -> Tuple[int, str]:
    """Returns (exit code, stdout text). Expected failures raise OSError or ValueError."""
    if args.command == "snapshot":
        cross = args.cross_style
        if cross is None:
            cross = _default_cross_style(args.workspace, args.style)
        data = snapshot(args.workspace, args.slug, args.style, args.dest, cross_style=cross, doc=args.doc)
        return 0, json.dumps(data, indent=2)
    if args.command == "check":
        problems = check(args.snapshot, args.kind)
        return (1, format_problems(problems)) if problems else (0, "")
    restore(args.snapshot)
    return 0, ""


def main(argv: List[str]) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        code, output = _dispatch(args)
    except (OSError, ValueError) as exc:
        # Missing page or style, bad names, a malformed snapshot: expected, reported as a Problem.
        print(format_problems([Problem("gate-error", args.command, "%s: %s" % (type(exc).__name__, exc))]))
        return 1
    if output:
        print(output)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
