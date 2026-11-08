from __future__ import annotations

import argparse
import sys
from urllib.parse import urlsplit
from urllib.request import url2pathname
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

# Runs as plain `python3`, never `-I`: isolated mode hides the user-site Playwright install.

NAVIGATION_TIMEOUT_MS = 10_000  # Longest a page load may take before Playwright raises.
READY_TIMEOUT_MS = 10_000  # Longest to wait for the shell's body[data-ready="true"].

READY = 'body[data-ready="true"]'
FRAME_LINKS_JS = """() => {
  const doc = document.getElementById('frame').contentDocument;
  const href = (id) => { const el = doc && doc.getElementById(id); return el ? el.getAttribute('href') || null : null; };
  return {style: href('sp-style'), layout: href('sp-layout')};
}"""


@dataclass
class VisitResult:
    console_errors: List[str] = field(default_factory=list)
    failed_requests: List[str] = field(default_factory=list)


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


LOCAL_HOSTS = ("127.0.0.1", "localhost")
INERT_SCHEMES = ("data", "about")
DEFAULT_PORTS = {"http": 80, "https": 443}


def _file_url_path(url: str) -> Optional[Path]:
    """The local path a file:// URL names, or None for a remote host or an unusable path."""
    parts = urlsplit(url)
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        return None
    try:
        return Path(url2pathname(parts.path))
    except ValueError:
        return None


def _origin(url: str) -> Tuple[str, Optional[str], Optional[int]]:
    parts = urlsplit(url)
    try:
        port = parts.port or DEFAULT_PORTS.get(parts.scheme)
    except ValueError:
        port = None
    return parts.scheme, parts.hostname, port


def _allow_for(page_url: str) -> Callable[[str], bool]:
    """The untrusted request gate for a page: data:/about:, plus either files under the page file's
    directory (file pages) or the page's own origin (http pages). Everything else, loopback included,
    is refused."""
    if urlsplit(page_url).scheme == "file":
        page = _file_url_path(page_url)
        if page is None:
            raise ValueError("cannot derive the allowed directory from %s" % page_url)
        root = page.resolve().parent

        def allow_file(url: str) -> bool:
            scheme = urlsplit(url).scheme
            if scheme in INERT_SCHEMES:
                return True
            target = _file_url_path(url) if scheme == "file" else None
            if target is None:
                return False
            try:
                resolved = target.resolve()
            except (OSError, RuntimeError, ValueError):
                return False
            return resolved == root or root in resolved.parents

        return allow_file
    origin = _origin(page_url)
    return lambda url: urlsplit(url).scheme in INERT_SCHEMES or _origin(url) == origin


def _open_page(
    playwright: Any, width: int = 1280, height: int = 900, untrusted: bool = False,
    blocked: Optional[List[str]] = None, url: Optional[str] = None,
) -> Any:
    if untrusted and url is None:
        raise ValueError("untrusted pages need their url to derive the allowed scope")
    allow = _allow_for(url) if untrusted and url is not None else None
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": width, "height": height}, java_script_enabled=not untrusted
    )
    if allow is not None:

        def gate(route: Any) -> None:
            if allow(route.request.url):
                route.continue_()
            else:
                if blocked is not None:
                    blocked.append(route.request.url)
                route.abort()

        context.route("**/*", gate)
    page = context.new_page()
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    return page


def _wait_ready(page: Any) -> None:
    page.wait_for_selector(READY, state="attached", timeout=READY_TIMEOUT_MS)
    _wait_idle(page)


def _wait_idle(page: Any) -> None:
    # Include fonts and images the style requests.
    page.wait_for_load_state("networkidle", timeout=READY_TIMEOUT_MS)


def read_body_state(url: str, interact: Optional[Callable[[Any], None]] = None) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        page = _open_page(pw)
        try:
            page.goto(url)
            _wait_ready(page)
            if interact is not None:
                interact(page)
                _wait_ready(page)
            state = page.evaluate(
                """() => {
                  const b = document.body;
                  const get = (n) => b.getAttribute(n);
                  return {
                    "data-page": get("data-page"), "data-style": get("data-style"),
                    "data-mode": get("data-mode"), "data-layout-applied": get("data-layout-applied"),
                    "data-ready": get("data-ready"), "text": b.innerText
                  };
                }"""
            )
            state["frame"] = page.evaluate(FRAME_LINKS_JS)
            return state
        finally:
            page.context.browser.close()


def measure_frame(url: str, script: str) -> Any:
    """Load the switcher shell at url, wait until the preview is styled, and return script's result.
    script is a JS arrow function evaluated in the shell page (the preview is #frame)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        page = _open_page(pw)
        try:
            page.goto(url)
            _wait_ready(page)
            return page.evaluate(script)
        finally:
            page.context.browser.close()


MAX_FULL_PAGE_HEIGHT = 8000


def _grow_viewport_to_frame(page: Any, width: int) -> None:
    """The switcher shell is one viewport tall and scrolls the preview inside its iframe, so a
    full-page shot of the shell shows one screen. Make the viewport tall enough for the frame's page."""
    needed = page.evaluate(
        """() => {
          const f = document.getElementById("frame");
          if (!f || !f.contentDocument) return 0;
          const top = f.getBoundingClientRect().top;
          return Math.ceil(top + f.contentDocument.documentElement.scrollHeight);
        }"""
    )
    if needed > 0:
        page.set_viewport_size({"width": width, "height": min(needed, MAX_FULL_PAGE_HEIGHT)})
        page.wait_for_timeout(200)


def screenshot(
    url: str, out: Path, width: int = 1280, height: int = 900, wait_ready: bool = False,
    untrusted: bool = False, full_page: bool = False,
) -> bool:
    """Screenshot url. untrusted=True is for saved pages and unpacked source sites: no scripts run;
    a file:// page may load only files under its own directory (plus data:/about:), any other page
    only its own origin."""
    if not playwright_available():
        return False
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        page = _open_page(pw, width, height, untrusted, url=url)
        try:
            page.goto(url)
            if wait_ready:
                _wait_ready(page)
            else:
                _wait_idle(page)
            if full_page:
                _grow_viewport_to_frame(page, width)
            page.screenshot(path=str(out), full_page=full_page)
            return True
        finally:
            page.context.browser.close()


def visit(url: str, wait_ready: bool = False, untrusted: bool = False) -> VisitResult:
    """Load url and record errors. untrusted=True is for saved pages and unpacked source sites: no
    scripts run; a file:// page may load only files under its own directory (plus data:/about:), any
    other page only its own origin. Blocked requests are reported in failed_requests."""
    from playwright.sync_api import sync_playwright

    result = VisitResult()
    with sync_playwright() as pw:
        blocked: List[str] = []
        page = _open_page(pw, untrusted=untrusted, blocked=blocked, url=url)

        def on_console(message: Any) -> None:
            # Chromium also logs our own aborts as console errors; those are reported as failed requests.
            if message.type == "error" and message.location.get("url") not in blocked:
                result.console_errors.append(message.text)

        page.on("console", on_console)
        page.on("pageerror", lambda e: result.console_errors.append(str(e)))
        page.on("requestfailed", lambda r: result.failed_requests.append("%s %s" % (r.failure, r.url)))
        page.on(
            "response",
            lambda r: result.failed_requests.append("%d %s" % (r.status, r.url)) if r.status >= 400 else None,
        )
        try:
            page.goto(url)
            if wait_ready:
                _wait_ready(page)
            else:
                _wait_idle(page)
            return result
        finally:
            page.context.browser.close()


EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NO_PLAYWRIGHT = 3


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Any:
        raise _UsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="screenshot.py", add_help=False)
    parser.add_argument("target")
    parser.add_argument("out")
    parser.add_argument("--untrusted", action="store_true")
    parser.add_argument("--trusted", action="store_true")
    parser.add_argument("--full-page", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--wait-ready", action="store_true")
    return parser


def _resolve_url(target: str) -> str:
    """The URL to load: an existing file path or file:// URL, or an http(s) loopback URL."""
    path = Path(target)
    if path.is_file():
        return path.resolve().as_uri()
    parts = urlsplit(target)
    if parts.scheme == "file":
        local = _file_url_path(target)
        if local is None:
            raise _UsageError("unsupported URL (file URLs must name a local file): %s" % target)
        if not local.is_file():
            raise _UsageError("file not found: %s" % local)
        return local.resolve().as_uri()
    if parts.scheme in ("http", "https") and parts.hostname in LOCAL_HOSTS:
        return target
    if parts.scheme:
        raise _UsageError("unsupported URL (only file:// and http(s)://127.0.0.1 or localhost): %s" % target)
    raise _UsageError("file not found: %s" % target)


def _parse(argv: List[str]) -> Any:
    args = _build_parser().parse_args(argv)
    if args.width < 1 or args.height < 1:
        raise _UsageError("--width and --height must be positive")
    if args.trusted and args.untrusted:
        raise _UsageError("--trusted and --untrusted are mutually exclusive")
    url = _resolve_url(args.target)
    # File targets (saved pages, unpacked sites) are untrusted unless --trusted; loopback targets the reverse.
    args.untrusted = args.untrusted or (urlsplit(url).scheme == "file" and not args.trusted)
    out = Path(args.out)
    if not out.parent.is_dir():
        raise _UsageError("output directory does not exist: %s" % out.parent)
    return args, url, out


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args, url, out = _parse(sys.argv[1:] if argv is None else argv)
    except _UsageError as e:
        sys.stderr.write("usage error: %s\n" % " ".join(str(e).split()))
        return EXIT_USAGE
    if not playwright_available():
        sys.stderr.write("Playwright is not available\n")
        return EXIT_NO_PLAYWRIGHT
    from playwright.sync_api import Error as PlaywrightError

    try:
        ok = screenshot(
            url, out, args.width, args.height, wait_ready=args.wait_ready,
            untrusted=args.untrusted, full_page=args.full_page,
        )
    except (PlaywrightError, OSError) as e:
        sys.stderr.write("screenshot failed: %s\n" % (str(e).strip().splitlines() or ["unknown error"])[0])
        return EXIT_FAILED
    if not ok:
        sys.stderr.write("screenshot failed\n")
        return EXIT_FAILED
    sys.stdout.write("%s\n" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
