from __future__ import annotations

import threading

import pytest

from fixtures.make_workspace import make_workspace
from manifest import write_manifest
from screenshot import playwright_available, read_body_state, screenshot, visit
from switcher import make_server

pytestmark = pytest.mark.skipif(not playwright_available(), reason="Playwright is not importable")

NOTE = "No layout in this style; showing style only"


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    ws = make_workspace(
        tmp_path_factory.mktemp("browser") / "ws",
        pages=[("home", "Home"), ("pricing", "Pricing")],
        styles=[("plain", None, False), ("bold", "Bold", True)],
    )
    # The shell probes each style's notes.md and a missing one is a 404, so give every style notes.
    for style in ("plain", "bold"):
        (ws / "styles" / style / "notes.md").write_text("notes", encoding="utf-8")
    write_manifest(ws)
    server = make_server(ws, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d/" % server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_screenshot_writes_png(base_url, tmp_path):
    out = tmp_path / "shot.png"
    assert screenshot(base_url, out, wait_ready=True) is True
    assert out.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_hash_selects_page_style_mode(base_url):
    state = read_body_state(base_url + "#p=pricing&s=bold&m=2")
    assert state["data-page"] == "pricing"
    assert state["data-style"] == "bold"
    assert state["data-mode"] == "2"


def test_mode_2_without_layout_is_soft(base_url):
    state = read_body_state(base_url + "#p=home&s=plain&m=2")
    assert state["data-layout-applied"] == "false"
    assert NOTE in state["text"]
    assert state["frame"]["layout"] is None


def test_mode_2_with_layout_applies_it(base_url):
    state = read_body_state(base_url + "#p=home&s=bold&m=2")
    assert state["data-layout-applied"] == "true"
    assert state["frame"]["layout"].endswith("/layout.css")


def test_mode_1_has_no_layout(base_url):
    state = read_body_state(base_url + "#p=home&s=bold&m=1")
    assert state["frame"]["layout"] is None
    assert state["frame"]["style"].endswith("/style.css")


def test_unstyled_has_no_style_link(base_url):
    state = read_body_state(base_url + "#p=home&s=&m=1")
    assert state["frame"]["style"] is None


def test_arrow_keys_move_between_pages(base_url):
    state = read_body_state(base_url + "#p=home&s=bold&m=1", interact=lambda page: page.keyboard.press("ArrowRight"))
    assert state["data-page"] == "pricing"
    state = read_body_state(base_url + "#p=pricing&s=bold&m=1", interact=lambda page: page.keyboard.press("ArrowLeft"))
    assert state["data-page"] == "home"


def test_dropdown_sets_style(base_url):
    state = read_body_state(base_url + "#p=home&s=plain&m=1", interact=lambda page: page.select_option("#style-select", "bold"))
    assert state["data-style"] == "bold"
    assert state["frame"]["style"].endswith("/style.css")


def test_next_disabled_on_last_page(base_url):
    seen = {}

    def interact(page):
        seen["disabled"] = page.is_disabled("#next")

    read_body_state(base_url + "#p=pricing&s=bold&m=1", interact=interact)
    assert seen["disabled"] is True


def test_unknown_slug_shows_error_banner(base_url):
    seen = {}

    def interact(page):
        seen["visible"] = page.is_visible("#error-banner")
        seen["text"] = page.inner_text("#error-banner")

    read_body_state(base_url + "#p=nope&s=bold&m=1", interact=interact)
    assert seen["visible"] is True
    assert "nope" in seen["text"]


def test_clean_shell_has_no_console_errors_or_failed_requests(base_url):
    result = visit(base_url + "#p=home&s=bold&m=2", wait_ready=True)
    assert result.console_errors == []
    assert result.failed_requests == []


@pytest.fixture
def live_workspace(tmp_path):
    """A workspace served for one test; yields (workspace, base_url)."""
    ws = make_workspace(tmp_path / "ws", styles=[("paint", None, False)])
    (ws / "styles" / "paint" / "style.css").write_text("body{background:rgb(1,2,3)}", encoding="utf-8")
    (ws / "styles" / "paint" / "notes.md").write_text("notes", encoding="utf-8")
    server = make_server(ws, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield ws, "http://127.0.0.1:%d/" % server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_ready_means_stylesheet_applied(live_workspace):
    _, url = live_workspace
    seen = {}

    def interact(page):
        def slow(route):
            page.wait_for_timeout(400)
            route.continue_()

        page.route("**/styles/paint/style.css", slow)
        page.select_option("#style-select", "paint")
        seen["ready_while_pending"] = page.get_attribute("body", "data-ready")
        page.wait_for_selector('body[data-ready="true"]')
        seen["bg"] = page.frame_locator("#frame").locator("body").evaluate("el => getComputedStyle(el).backgroundColor")

    read_body_state(url + "#p=home&s=&m=1", interact=interact)
    assert seen["ready_while_pending"] == "false"
    assert seen["bg"] == "rgb(1, 2, 3)"


def test_missing_stylesheet_shows_banner_and_still_ready(live_workspace):
    ws, url = live_workspace
    (ws / "styles" / "paint" / "style.css").unlink()
    seen = {}

    def interact(page):
        seen["visible"] = page.is_visible("#error-banner")
        seen["text"] = page.inner_text("#error-banner")

    state = read_body_state(url + "#p=home&s=paint&m=1", interact=interact)
    assert seen["visible"] is True
    assert "/w/styles/paint/style.css" in seen["text"]
    assert state["data-ready"] == "true"


def test_stylesheet_error_banner_survives_rerender_until_failure_clears(tmp_path):
    ws = make_workspace(tmp_path / "ws", styles=[("broken", None, False), ("good", None, False)])
    for style in ("broken", "good"):
        (ws / "styles" / style / "notes.md").write_text("notes", encoding="utf-8")
    write_manifest(ws)
    server = make_server(ws, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Deleted after the server started, so the shell sees a manifest entry whose style.css 404s.
    (ws / "styles" / "broken" / "style.css").unlink()
    seen = {}

    def snapshot(page, key):
        seen[key] = (page.is_visible("#error-banner"), page.inner_text("#error-banner"))

    def interact(page):
        snapshot(page, "loaded")
        page.click("#mode-toggle")
        page.wait_for_selector('body[data-mode="2"][data-ready="true"]')
        snapshot(page, "toggled")
        page.select_option("#style-select", "good")
        page.wait_for_selector('body[data-style="good"][data-ready="true"]')
        snapshot(page, "switched")

    try:
        read_body_state("http://127.0.0.1:%d/#s=broken&m=1" % server.server_address[1], interact=interact)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    href = "/w/styles/broken/style.css"
    assert seen["loaded"][0] is True and href in seen["loaded"][1]
    assert seen["toggled"][0] is True and href in seen["toggled"][1]
    assert seen["switched"][0] is False


def test_stale_notes_failure_shows_no_banner(base_url):
    seen = {}

    def interact(page):
        def fail_late(route):
            page.wait_for_timeout(500)
            route.abort()

        page.route("**/styles/plain/notes.md", fail_late)
        page.select_option("#style-select", "plain")
        page.select_option("#style-select", "bold")
        page.wait_for_selector('body[data-style="bold"][data-ready="true"]')
        page.wait_for_timeout(1000)
        seen["visible"] = page.is_visible("#error-banner")

    read_body_state(base_url + "#p=home&s=&m=1", interact=interact)
    assert seen["visible"] is False


def test_untrusted_visit_blocks_scripts_and_remote_requests(tmp_path):
    page = tmp_path / "saved.html"
    page.write_text(
        '<html><body><script>console.error("ran")</script>'
        '<img src="https://example.invalid/x.png"></body></html>',
        encoding="utf-8",
    )
    result = visit(page.as_uri(), untrusted=True)
    assert result.console_errors == []
    assert any("https://example.invalid/x.png" in r for r in result.failed_requests)


def test_trusted_visit_runs_scripts(tmp_path):
    page = tmp_path / "saved.html"
    page.write_text('<html><body><script>console.error("ran")</script></body></html>', encoding="utf-8")
    assert "ran" in visit(page.as_uri()).console_errors


def test_default_mode_is_2(base_url):
    state = read_body_state(base_url + "#p=home&s=bold")
    assert state["data-mode"] == "2"
    assert state["data-layout-applied"] == "true"
    assert read_body_state(base_url)["data-mode"] == "2"


def test_no_layout_note_is_a_prominent_bar(base_url):
    seen = {}

    def interact(page):
        seen.update(page.evaluate(
            """() => {
              const n = document.getElementById("layout-note");
              const r = n.getBoundingClientRect();
              const bg = getComputedStyle(n).backgroundColor;
              return { hidden: n.hidden, width: r.width, vw: window.innerWidth, bg: bg };
            }"""
        ))

    read_body_state(base_url + "#p=home&s=plain", interact=interact)
    assert seen["hidden"] is False
    assert seen["width"] >= seen["vw"] * 0.95
    assert seen["bg"] not in ("rgba(0, 0, 0, 0)", "transparent")


def test_layout_note_is_hidden_when_style_has_layout(base_url):
    seen = {}
    read_body_state(base_url + "#p=home&s=bold", interact=lambda page: seen.update(hidden=page.is_hidden("#layout-note")))
    assert seen["hidden"] is True


def _frame_width(page):
    return page.evaluate('() => document.getElementById("frame").getBoundingClientRect().width')


def test_viewport_width_control_sets_frame_width_and_hash(base_url):
    seen = {}

    def interact(page):
        seen["fit"] = _frame_width(page)
        page.select_option("#width-select", "768")
        page.wait_for_selector('body[data-ready="true"]')
        seen["narrow"] = _frame_width(page)
        seen["hash"] = page.evaluate("location.hash")
        seen["inner"] = page.evaluate('() => document.getElementById("frame").contentWindow.innerWidth')

    read_body_state(base_url + "#p=home&s=bold", interact=interact)
    assert seen["fit"] > 768
    assert round(seen["narrow"]) == 768
    assert round(seen["inner"]) == 768
    assert "w=768" in seen["hash"]


def test_width_from_hash(base_url):
    seen = {}
    read_body_state(base_url + "#p=home&s=bold&m=2&w=768", interact=lambda page: seen.update(w=_frame_width(page), sel=page.input_value("#width-select")))
    assert round(seen["w"]) == 768
    assert seen["sel"] == "768"


def test_unknown_width_shows_banner(base_url):
    seen = {}
    read_body_state(base_url + "#p=home&s=bold&w=abc", interact=lambda page: seen.update(text=page.inner_text("#error-banner"), sel=page.input_value("#width-select")))
    assert "abc" in seen["text"]
    assert seen["sel"] == ""
