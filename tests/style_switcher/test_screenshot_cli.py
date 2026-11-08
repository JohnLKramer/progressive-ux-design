from __future__ import annotations

import struct
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from screenshot import playwright_available, screenshot, visit

needs_browser = pytest.mark.skipif(not playwright_available(), reason="Playwright is not importable")
SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "style-switcher" / "scripts" / "screenshot.py"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

TALL = "<html><body style='margin:0'><div style='height:3000px'>tall</div></body></html>"
HOSTILE = (
    "<html><head><script>document.title='x'</script></head>"
    "<body><img src='https://example.invalid/x.png'>hi</body></html>"
)


def png_size(path: Path):
    data = path.read_bytes()
    assert data.startswith(PNG_SIGNATURE)
    return struct.unpack(">II", data[16:24])


def run_cli(*args):
    # Plain interpreter, no -I; PLAYWRIGHT_BROWSERS_PATH is inherited from the environment.
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=120
    )


def write_page(tmp_path, html, name="page.html"):
    page = tmp_path / name
    page.write_text(html, encoding="utf-8")
    return page


def assert_usage_error(proc):
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert len(proc.stderr.strip().splitlines()) == 1


@needs_browser
def test_full_page_is_taller_than_viewport(tmp_path):
    page = write_page(tmp_path, TALL)
    plain, full = tmp_path / "plain.png", tmp_path / "full.png"
    assert screenshot(page.as_uri(), plain, width=800, height=600) is True
    assert screenshot(page.as_uri(), full, width=800, height=600, full_page=True) is True
    assert png_size(plain) == (800, 600)
    assert png_size(full)[1] >= 3000


def test_no_args_is_usage_error():
    assert_usage_error(run_cli())


def test_unknown_flag_is_usage_error(tmp_path):
    page = write_page(tmp_path, TALL)
    assert_usage_error(run_cli(page, tmp_path / "o.png", "--bogus"))


@pytest.mark.parametrize("url", ["https://example.com/", "http://example.com/", "ftp://127.0.0.1/x", "data:text/html,hi"])
def test_non_local_url_is_refused(tmp_path, url):
    assert_usage_error(run_cli(url, tmp_path / "o.png"))
    assert not (tmp_path / "o.png").exists()


def test_missing_parent_dir_is_usage_error(tmp_path):
    page = write_page(tmp_path, TALL)
    assert_usage_error(run_cli(page, tmp_path / "nope" / "o.png"))
    assert not (tmp_path / "nope").exists()


def test_nonexistent_path_is_usage_error(tmp_path):
    assert_usage_error(run_cli(tmp_path / "missing.html", tmp_path / "o.png"))


@needs_browser
def test_cli_success_on_local_file(tmp_path):
    page = write_page(tmp_path, TALL)
    out = tmp_path / "o.png"
    proc = run_cli(page, out, "--width", "500", "--height", "400")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines() == [str(out)]
    assert png_size(out) == (500, 400)


@needs_browser
def test_cli_full_page_flag(tmp_path):
    page = write_page(tmp_path, TALL)
    out = tmp_path / "o.png"
    assert run_cli(page, out, "--full-page", "--width", "500", "--height", "400").returncode == 0
    assert png_size(out)[1] >= 3000


@needs_browser
def test_cli_untrusted_blocks_script_and_network(tmp_path):
    page = write_page(tmp_path, HOSTILE)
    out = tmp_path / "o.png"
    proc = run_cli(page, out, "--untrusted")
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    assert out.read_bytes().startswith(PNG_SIGNATURE)


@needs_browser
def test_cli_accepts_loopback_url_form(tmp_path):
    # A loopback URL with nothing listening is an expected screenshot failure: exit 1, one line.
    proc = run_cli("http://127.0.0.1:9/", tmp_path / "o.png")
    assert proc.returncode == 1
    assert len(proc.stderr.strip().splitlines()) == 1


# ---- file:// targets and the untrusted scope ----------------------------------------------

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082"
)


class Loopback:
    """A 127.0.0.1 http server that records every request path it receives."""

    def __init__(self, pages=None):
        hits = self.hits = []
        served = self.served = pages or {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                kind, body = served.get(self.path, ("image/png", PNG_1PX))
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.end_headers()
                self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


@pytest.fixture
def outside_file(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.png"
    secret.write_bytes(PNG_1PX)
    return secret


def site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    return root


@needs_browser
def test_untrusted_file_page_blocks_files_outside_its_directory(tmp_path, outside_file):
    root = site(tmp_path)
    (root / "frame.html").write_text("<p>frame</p>", encoding="utf-8")
    page = write_page(root, "<img src='%s'><iframe src='%s'></iframe>"
                      % (outside_file.as_uri(), (outside_file.parent / "secret.png").as_uri()))
    result = visit(page.as_uri(), untrusted=True)
    assert any(outside_file.as_uri() in f for f in result.failed_requests), result.failed_requests
    assert len([f for f in result.failed_requests if outside_file.as_uri() in f]) >= 1


@needs_browser
def test_untrusted_file_page_blocks_outside_iframe_document(tmp_path):
    root = site(tmp_path)
    other = tmp_path / "other.html"
    other.write_text("<p>other</p>", encoding="utf-8")
    page = write_page(root, "<iframe src='%s'></iframe>" % other.as_uri())
    result = visit(page.as_uri(), untrusted=True)
    assert any(other.as_uri() in f for f in result.failed_requests), result.failed_requests


@needs_browser
def test_untrusted_file_page_blocks_dotdot_escape(tmp_path, outside_file):
    root = site(tmp_path)
    page = write_page(root, "<img src='../outside/secret.png'>")
    result = visit(page.as_uri(), untrusted=True)
    assert any("secret.png" in f for f in result.failed_requests), result.failed_requests


@needs_browser
def test_untrusted_file_page_loads_sibling_and_nested_assets(tmp_path):
    root = site(tmp_path)
    (root / "page_files").mkdir()
    (root / "a.png").write_bytes(PNG_1PX)
    (root / "page_files" / "b.png").write_bytes(PNG_1PX)
    page = write_page(root, "<img src='a.png'><img src='page_files/b.png'><img src='data:image/png;base64,AAAA'>")
    result = visit(page.as_uri(), untrusted=True)
    assert result.failed_requests == [] or all("data:" in f for f in result.failed_requests)
    assert not any("a.png" in f or "b.png" in f for f in result.failed_requests)


@needs_browser
def test_untrusted_file_page_blocks_symlink_escaping_its_directory(tmp_path, outside_file):
    root = site(tmp_path)
    (root / "link.png").symlink_to(outside_file)
    page = write_page(root, "<img src='link.png'>")
    result = visit(page.as_uri(), untrusted=True)
    assert any("link.png" in f for f in result.failed_requests), result.failed_requests


@needs_browser
def test_untrusted_file_page_cannot_reach_loopback(tmp_path):
    root = site(tmp_path)
    with Loopback() as server:
        page = write_page(root, "<img src='%s/a.png'><iframe src='%s/b.html'></iframe>" % (server.url, server.url))
        result = visit(page.as_uri(), untrusted=True)
    assert server.hits == []
    assert any("127.0.0.1" in f for f in result.failed_requests), result.failed_requests


@needs_browser
def test_untrusted_loopback_target_allows_only_its_own_origin():
    with Loopback() as other, Loopback() as own:
        page = "<img src='/own.png'><img src='%s/other.png'><img src='file:///etc/hosts'>" % other.url
        own.served["/page"] = ("text/html", page)
        result = visit(own.url + "/page", untrusted=True)
    assert sorted(own.hits) == ["/own.png", "/page"]
    assert other.hits == []
    assert any(other.url in f for f in result.failed_requests)


@needs_browser
def test_untrusted_page_scripts_do_not_run_trusted_ones_do(tmp_path):
    page = write_page(site(tmp_path), "<script>console.error('ran')</script>hi")
    assert visit(page.as_uri(), untrusted=True).console_errors == []
    assert visit(page.as_uri(), untrusted=False).console_errors == ["ran"]


@needs_browser
def test_screenshot_untrusted_file_derives_scope_from_url(tmp_path, outside_file):
    root = site(tmp_path)
    page = write_page(root, "<img src='%s'>hi" % outside_file.as_uri())
    out = tmp_path / "o.png"
    assert screenshot(page.as_uri(), out, untrusted=True) is True
    assert out.read_bytes().startswith(PNG_SIGNATURE)


@needs_browser
def test_cli_file_target_is_untrusted_by_default(tmp_path):
    page = write_page(site(tmp_path), "<script>new Image().src='%s/ran'</script>hi" % "{URL}")
    with Loopback() as server:
        page.write_text(page.read_text(encoding="utf-8").replace("{URL}", server.url), encoding="utf-8")
        assert run_cli(page, tmp_path / "a.png").returncode == 0
        assert server.hits == []
        assert run_cli(page, tmp_path / "b.png", "--untrusted").returncode == 0
        assert server.hits == []
        proc = run_cli(page, tmp_path / "c.png", "--trusted")
        assert proc.returncode == 0, proc.stderr
        assert server.hits == ["/ran"]


def test_trusted_and_untrusted_together_is_usage_error(tmp_path):
    page = write_page(site(tmp_path), TALL)
    assert_usage_error(run_cli(page, tmp_path / "o.png", "--trusted", "--untrusted"))


@needs_browser
def test_cli_accepts_file_url_for_existing_file(tmp_path):
    page = write_page(site(tmp_path), TALL)
    out = tmp_path / "o.png"
    proc = run_cli(page.as_uri(), out, "--width", "300", "--height", "200")
    assert proc.returncode == 0, proc.stderr
    assert png_size(out) == (300, 200)


@needs_browser
def test_cli_accepts_percent_encoded_file_url(tmp_path):
    page = write_page(site(tmp_path), TALL, name="my page.html")
    proc = run_cli(page.as_uri(), tmp_path / "o.png")
    assert proc.returncode == 0, proc.stderr


def test_missing_file_url_says_file_not_found(tmp_path):
    proc = run_cli((tmp_path / "nope.html").as_uri(), tmp_path / "o.png")
    assert_usage_error(proc)
    assert "file not found" in proc.stderr
    assert "unsupported URL" not in proc.stderr


def test_directory_file_url_says_file_not_found(tmp_path):
    proc = run_cli(tmp_path.as_uri(), tmp_path / "o.png")
    assert_usage_error(proc)
    assert "file not found" in proc.stderr


@pytest.mark.parametrize("url", ["file://example.com/etc/hosts", "https://example.com/", "ftp://127.0.0.1/x"])
def test_unsupported_url_message(tmp_path, url):
    proc = run_cli(url, tmp_path / "o.png")
    assert_usage_error(proc)
    assert "unsupported URL" in proc.stderr
    assert "file not found" not in proc.stderr
