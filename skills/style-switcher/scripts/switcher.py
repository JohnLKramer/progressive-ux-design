from __future__ import annotations

import http.server
import mimetypes
import sys
import webbrowser
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from manifest import MANIFEST_NAME, validate_manifest, write_manifest  # noqa: E402
from problems import Problem, ValidationError  # noqa: E402
from validate_page import validate_page  # noqa: E402
from validate_style import validate_style  # noqa: E402

SHELL_DIR = Path(__file__).resolve().parent.parent / "shell"
USAGE = "usage: switcher.py <workspace> [--no-open]"

CONTENT_TYPES = {
    ".md": "text/plain; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".woff2": "font/woff2",
}


def content_type(path: Path) -> str:
    override = CONTENT_TYPES.get(path.suffix.lower())
    if override:
        return override
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def resolve_under(root: Path, relative: str) -> Optional[Path]:
    """Resolve `relative` (already percent-decoded) under root; None if it escapes or is not a file."""
    if "\x00" in relative:
        return None
    candidate = (root / relative.lstrip("/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


class SwitcherServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, workspace_root: Path, port: int) -> None:
        self.workspace_root = workspace_root
        self.shell_root = SHELL_DIR.resolve()
        super().__init__(("127.0.0.1", port), SwitcherHandler)


class SwitcherHandler(http.server.BaseHTTPRequestHandler):
    server: SwitcherServer

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _route(self) -> Optional[Path]:
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            return resolve_under(self.server.shell_root, "index.html")
        if path == "/manifest.json":
            return resolve_under(self.server.workspace_root, MANIFEST_NAME)
        if path.startswith("/shell/"):
            return resolve_under(self.server.shell_root, path[len("/shell/"):])
        if path.startswith("/w/"):
            return resolve_under(self.server.workspace_root, path[len("/w/"):])
        return None

    def _send(self, status: int, body: bytes, ctype: str = "text/plain; charset=utf-8", extra: Optional[dict] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        target = self._route()
        if target is None:
            self._send(404, b"not found\n")
            return
        self._send(200, target.read_bytes(), content_type(target))

    def _method_not_allowed(self) -> None:
        self._send(405, b"method not allowed\n", extra={"Allow": "GET"})

    do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _method_not_allowed


def collect_problems(workspace: Path) -> List[Problem]:
    problems = list(validate_manifest(workspace))
    for page_dir in sorted((workspace / "pages").glob("*/")):
        index = page_dir / "index.html"
        if index.is_file():
            problems.extend(validate_page(index))
    for style_dir in sorted((workspace / "styles").glob("*/")):
        problems.extend(validate_style(style_dir))
    return problems


def make_server(workspace: Path, port: int = 0) -> http.server.ThreadingHTTPServer:
    """Rebuild the manifest, validate manifest, pages and styles, and bind a server; raises with all problems."""
    workspace = Path(workspace)
    write_manifest(workspace)
    problems = collect_problems(workspace)
    if problems:
        raise ValidationError(problems)
    return SwitcherServer(workspace.resolve(), port)


def open_and_serve(server: http.server.HTTPServer, url: str, opener: Optional[Callable[[str], bool]]) -> None:
    """Open the URL with `opener` (skipped when None), then serve until interrupted."""
    if opener is not None and not opener(url):
        print("could not open a browser; open the URL above", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: List[str]) -> int:
    args = [a for a in argv if a != "--no-open"]
    if len(args) != 1 or args[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    workspace = Path(args[0])
    if not workspace.is_dir():
        print("error: workspace directory not found: %s" % workspace, file=sys.stderr)
        return 1
    try:
        server = make_server(workspace)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print(url, flush=True)
    open_and_serve(server, url, None if "--no-open" in argv else webbrowser.open)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
