from __future__ import annotations

import http.client
import json
import shutil
import threading

import pytest

from fixtures.make_workspace import make_workspace
from manifest import build_manifest, write_manifest
from problems import ValidationError
import switcher
from switcher import make_server, main, open_and_serve


@pytest.fixture
def served(tmp_path):
    ws = make_workspace(tmp_path / "ws", styles=[("plain", None, False), ("bold", "Bold", True)])
    write_manifest(ws)
    server = make_server(ws, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield ws, server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def request(server, path, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def test_manifest_json_served(served):
    ws, server = served
    status, headers, body = request(server, "/manifest.json")
    assert status == 200
    assert body == (ws / "manifest.json").read_bytes()
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"
    assert [s["id"] for s in json.loads(body)["styles"]] == ["bold", "plain"]


def test_workspace_page_served(served):
    ws, server = served
    status, headers, body = request(server, "/w/pages/home/index.html?x=1")
    assert status == 200
    assert body == (ws / "pages" / "home" / "index.html").read_bytes()
    assert headers["Content-Type"] == "text/html; charset=utf-8"


def test_shell_served(served):
    _, server = served
    status, headers, body = request(server, "/")
    assert status == 200
    assert b'id="frame"' in body
    for name, ctype in (("shell.js", "text/javascript; charset=utf-8"), ("shell.css", "text/css; charset=utf-8")):
        status, headers, _ = request(server, "/shell/" + name)
        assert status == 200
        assert headers["Content-Type"] == ctype


def test_notes_md_is_text_plain(served):
    ws, server = served
    (ws / "styles" / "bold" / "notes.md").write_text("# hi", encoding="utf-8")
    status, headers, _ = request(server, "/w/styles/bold/notes.md")
    assert status == 200
    assert headers["Content-Type"] == "text/plain; charset=utf-8"


MARKER = "SECRET-MARKER-7f3c9a1e"


@pytest.fixture
def secret(served, tmp_path):
    (tmp_path / "secret.txt").write_text(MARKER, encoding="utf-8")


@pytest.mark.parametrize(
    "path, forbidden",
    [
        ("/w/../secret.txt", MARKER),
        ("/w/%2e%2e/secret.txt", MARKER),
        ("/w/%2E%2E/secret.txt", MARKER),
        ("/w/%252e%252e/secret.txt", MARKER),
        ("/shell/../scripts/switcher.py", "def main"),
        ("/shell/%2e%2e/scripts/switcher.py", "def main"),
    ],
)
def test_traversal_to_real_outside_file_404(served, secret, path, forbidden):
    _, server = served
    status, _, body = request(server, path)
    assert status == 404
    assert forbidden.encode() not in body


@pytest.mark.parametrize(
    "path",
    [
        "/w/pages/home/index.html%00",
        "/w/pages",
        "/w/pages/",
        "/w/missing.txt",
        "/nope",
    ],
)
def test_unsafe_or_missing_paths_404(served, path):
    _, server = served
    assert request(server, path)[0] == 404


def test_symlink_to_outside_file_404(served, tmp_path):
    ws, server = served
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    outside.write_text(MARKER, encoding="utf-8")
    (ws / "link.txt").symlink_to(outside)
    status, _, body = request(server, "/w/link.txt")
    assert status == 404
    assert MARKER.encode() not in body


def test_symlink_to_outside_dir_404(served, tmp_path):
    ws, server = served
    outside = tmp_path / "outdir"
    outside.mkdir()
    (outside / "f.txt").write_text(MARKER, encoding="utf-8")
    (ws / "linkdir").symlink_to(outside, target_is_directory=True)
    status, _, body = request(server, "/w/linkdir/f.txt")
    assert status == 404
    assert MARKER.encode() not in body


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_non_get_is_405(served, method):
    _, server = served
    status, headers, _ = request(server, "/manifest.json", method=method)
    assert status == 405
    assert headers["Allow"] == "GET"


def test_binds_loopback_only(served):
    _, server = served
    assert server.server_address[0] == "127.0.0.1"


def test_make_server_rejects_workspace_without_styles(tmp_path):
    ws = make_workspace(tmp_path / "ws", styles=[])
    write_manifest(ws)
    with pytest.raises(ValidationError) as exc:
        make_server(ws)
    assert any(p.code == "empty" for p in exc.value.problems)


def test_make_server_rebuilds_manifest_when_missing(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    server = make_server(ws)
    try:
        assert json.loads((ws / "manifest.json").read_text(encoding="utf-8")) == build_manifest(ws)
    finally:
        server.server_close()


def test_served_manifest_equals_build_manifest(served):
    ws, server = served
    _, _, body = request(server, "/manifest.json")
    assert json.loads(body) == build_manifest(ws)


def test_make_server_replaces_stale_manifest(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    (ws / "manifest.json").write_text("not json {", encoding="utf-8")
    server = make_server(ws)
    server.server_close()
    assert json.loads((ws / "manifest.json").read_text(encoding="utf-8")) == build_manifest(ws)


def served_manifest(ws):
    server = make_server(ws)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _, _, body = request(server, "/manifest.json")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return json.loads(body)


def codes(exc):
    return {p.code for p in exc.value.problems}


def test_make_server_reports_remote_url_in_style(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    (ws / "styles" / "plain" / "style.css").write_text("@font-face{src:url(https://x/y.woff)}", encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        make_server(ws)
    assert "remote-url" in codes(exc)


def test_make_server_reports_script_in_page(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    page = ws / "pages" / "home" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace("<body>", "<body><script>1</script>"), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        make_server(ws)
    assert "script" in codes(exc)


def test_make_server_reports_all_problems_together(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    (ws / "styles" / "plain" / "style.css").write_text("a{background:url(https://x/y.png)}", encoding="utf-8")
    page = ws / "pages" / "home" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace("<body>", "<body><script>1</script>"), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        make_server(ws)
    assert {"remote-url", "script"} <= codes(exc)


def test_style_added_after_first_manifest_is_served(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    write_manifest(ws)
    make_workspace(tmp_path / "other", styles=[("late", None, False)])
    shutil.copytree(tmp_path / "other" / "styles" / "late", ws / "styles" / "late")
    assert [s["id"] for s in served_manifest(ws)["styles"]] == ["late", "plain"]


def test_layout_added_later_flips_has_layout(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    write_manifest(ws)
    (ws / "styles" / "plain" / "layout.css").write_text(".x{margin:0}", encoding="utf-8")
    assert served_manifest(ws)["styles"][0]["hasLayout"] is True


def test_main_bad_workspace_returns_1(tmp_path, capsys):
    ws = make_workspace(tmp_path / "ws", styles=[])
    assert main([str(ws), "--no-open"]) == 1
    assert "empty" in capsys.readouterr().err


def test_main_usage_error_returns_2(capsys):
    assert main([]) == 2


class FakeServer:
    def __init__(self):
        self.served = False
        self.closed = False

    def serve_forever(self):
        self.served = True
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


def test_open_and_serve_opens_browser_once(capsys):
    opened = []
    server = FakeServer()
    open_and_serve(server, "http://x/", lambda url: opened.append(url) or True)
    assert opened == ["http://x/"]
    assert server.served and server.closed


@pytest.fixture
def main_env(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path / "ws")
    write_manifest(ws)
    opened = []
    monkeypatch.setattr(switcher.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(switcher.SwitcherServer, "serve_forever", lambda self: None)
    return ws, opened


def test_main_no_open_never_calls_browser(main_env):
    ws, opened = main_env
    assert main([str(ws), "--no-open"]) == 0
    assert opened == []


def test_main_opens_browser_once_with_url(main_env):
    ws, opened = main_env
    assert main([str(ws)]) == 0
    assert len(opened) == 1
    assert opened[0].startswith("http://127.0.0.1:")


def test_open_and_serve_opener_false_warns_and_serves(capsys):
    server = FakeServer()
    open_and_serve(server, "http://x/", lambda url: False)
    assert "could not open a browser; open the URL above" in capsys.readouterr().err
    assert server.served and server.closed
