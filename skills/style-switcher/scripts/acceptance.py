from __future__ import annotations

import html
import json
import shutil
import sys
import threading
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

import screenshot  # noqa: E402
from problems import Problem  # noqa: E402
from switcher import make_server  # noqa: E402
from visual_check import MEASURE_JS, evaluate_visual  # noqa: E402
from validate_page import _srcset_urls  # noqa: E402
from validate_style import _IMPORT_STR, _URL_FN, _strip_comments  # noqa: E402

# Runs as plain `python3`, never `-I`: isolated mode hides the user-site Playwright install.

EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NO_PLAYWRIGHT = 3

MODES = (1, 2)
URL_ATTRS = ("src", "href", "poster", "srcset")
SKIPPED_SCHEMES = ("data:", "http:", "https:", "mailto:", "tel:", "javascript:", "//")
NO_LAYOUT_NOTE = "no layout.css in this style; the shell shows the style alone"


def _is_checkable(reference: str) -> bool:
    ref = reference.strip()
    return bool(ref) and not ref.startswith("#") and not ref.lower().startswith(SKIPPED_SCHEMES)


def _resolve_problem(workspace: Path, source: Path, reference: str) -> Optional[Problem]:
    where = str(source.relative_to(workspace))
    path_part = unquote(urlsplit(reference.strip()).path)
    if not path_part:
        return None
    base = workspace if path_part.startswith("/") else source.parent
    target = (base / path_part.lstrip("/")).resolve()
    if workspace != target and workspace not in target.parents:
        return Problem("missing-file", where, "%s escapes the workspace" % reference)
    if not target.is_file():
        return Problem("missing-file", where, "%s does not exist" % reference)
    return None


class _RefScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: List[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        seen = set()
        for name, value in attrs:
            name = name.lower()
            if name in seen or name not in URL_ATTRS or not value:
                continue
            seen.add(name)
            self.refs.extend(_srcset_urls(value) if name == "srcset" else [value])


def _css_refs(css: str) -> List[str]:
    css = _strip_comments(css)
    refs: List[str] = []
    for pattern in (_URL_FN, _IMPORT_STR):
        for match in pattern.finditer(css):
            refs.append(next(g for g in match.groups() if g is not None).strip())
    return refs


def check_assets(workspace: Path) -> List[Problem]:
    """Every file a page or style CSS points at (src, href, url()) exists inside the workspace."""
    workspace = Path(workspace).resolve()
    sources: List[Tuple[Path, List[str]]] = []
    for page in sorted(workspace.glob("pages/*/*.html")):
        scanner = _RefScanner()
        scanner.feed(page.read_text(encoding="utf-8"))
        scanner.close()
        sources.append((page, scanner.refs))
    for name in ("style.css", "layout.css"):
        for css in sorted(workspace.glob("styles/*/" + name)):
            sources.append((css, _css_refs(css.read_text(encoding="utf-8"))))
    problems: List[Problem] = []
    for source, refs in sources:
        for ref in refs:
            if _is_checkable(ref):
                problem = _resolve_problem(workspace, source, ref)
                if problem is not None:
                    problems.append(problem)
    return problems


def _combinations(manifest: dict) -> List[Tuple[dict, dict, int]]:
    return [(style, page, mode) for style in manifest["styles"] for page in manifest["pages"] for mode in MODES]


def _shot_name(style: dict, page: dict, mode: int) -> str:
    return "%s--%s--m%d.png" % (style["id"], page["slug"], mode)


def _write_contact(out_dir: Path, manifest: dict, combos: List[Tuple[dict, dict, int]]) -> Path:
    parts = [
        "<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>Style switcher acceptance</title></head><body>",
        "<h1>Style switcher acceptance</h1>",
        "<p>%d combinations: %d styles, %d pages, 2 modes (1 = style only, 2 = style plus layout).</p>"
        % (len(combos), len(manifest["styles"]), len(manifest["pages"])),
    ]
    current: Optional[str] = None
    for style, page, mode in combos:
        if style["id"] != current:
            current = style["id"]
            parts.append(
                "<h2>%s</h2><p><a href=\"notes/%s.md\">notes.md</a></p>"
                % (html.escape(style["name"]), html.escape(style["id"], quote=True))
            )
        label = "%s, mode %d" % (page["title"], mode)
        if mode == 2 and not style["hasLayout"]:
            label += " (%s)" % NO_LAYOUT_NOTE
        parts.append(
            "<h3>%s</h3><p><img src=\"shots/%s\" alt=\"%s\" width=\"640\"></p>"
            % (html.escape(label), html.escape(_shot_name(style, page, mode), quote=True), html.escape(label, quote=True))
        )
    parts.append("</body></html>")
    path = out_dir / "contact.html"
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def run_acceptance(workspace: Path, out_dir: Path) -> int:
    workspace, out_dir = Path(workspace), Path(out_dir)
    if not screenshot.playwright_available():
        sys.stderr.write("Playwright is not available\n")
        return EXIT_NO_PLAYWRIGHT
    server = make_server(workspace)  # also rebuilds the manifest and validates everything
    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))

    failures: List[str] = ["%s: %s: %s" % (p.code, p.where, p.message) for p in check_assets(workspace)]
    for style in manifest["styles"]:
        if not (workspace / "styles" / style["id"] / "notes.md").is_file():
            failures.append("missing-notes: styles/%s: notes.md does not exist" % style["id"])
    if not manifest["pages"] or not manifest["styles"]:
        failures.append("empty: the workspace needs at least one page and one style")

    shots, notes = out_dir / "shots", out_dir / "notes"
    shots.mkdir(parents=True, exist_ok=True)
    notes.mkdir(parents=True, exist_ok=True)
    for style in manifest["styles"]:
        source = workspace / "styles" / style["id"] / "notes.md"
        if source.is_file():
            shutil.copyfile(str(source), str(notes / ("%s.md" % style["id"])))

    combos = _combinations(manifest)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%d/" % server.server_address[1]
    try:
        for style, page, mode in combos:
            url = base + "#p=%s&s=%s&m=%d" % (page["slug"], style["id"], mode)
            where = "%s / %s / mode %d" % (style["id"], page["slug"], mode)
            result = screenshot.visit(url, wait_ready=True)
            failures.extend("console-error: %s: %s" % (where, e) for e in result.console_errors)
            failures.extend("failed-request: %s: %s" % (where, r) for r in result.failed_requests)
            measured = screenshot.measure_frame(url, MEASURE_JS)
            layout_applied = mode == 2 and style["hasLayout"]
            failures.extend("%s: %s" % (problem, where) for problem in evaluate_visual(measured, layout_applied))
            if not screenshot.screenshot(url, shots / _shot_name(style, page, mode), wait_ready=True, full_page=True):
                failures.append("screenshot: %s: not written" % where)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    contact = _write_contact(out_dir, manifest, combos)
    print("%d combinations visited; contact sheet: %s" % (len(combos), contact))
    if failures:
        sys.stderr.write("%d failure(s):\n%s\n" % (len(failures), "\n".join(failures)))
        return EXIT_FAILED
    print("acceptance passed")
    return 0


USAGE = "usage: acceptance.py <workspace> <out-dir>"


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[0].startswith("-"):
        sys.stderr.write(USAGE + "\n")
        return EXIT_USAGE
    workspace = Path(argv[0])
    if not workspace.is_dir():
        sys.stderr.write("workspace directory not found: %s\n" % workspace)
        return EXIT_USAGE
    return run_acceptance(workspace, Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
