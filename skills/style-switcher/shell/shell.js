// Body attributes for tests and tooling:
//   data-page, data-style, data-mode  current selection.
//   data-layout-applied               "true" only when the loaded page's #sp-layout has an href.
//   data-ready                        "false" from the moment a page navigation starts until the
//                                     iframe's load handler has applied style and mode and every slot stylesheet
//                                     with an href has loaded or failed (a failure shows in the banner), then "true".
//                                     Wait for body[data-ready="true"] before asserting.
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    prev: $("prev"), next: $("next"), counter: $("counter"), title: $("title"),
    select: $("style-select"), width: $("width-select"), mode: $("mode-toggle"), notes: $("notes-link"),
    layoutNote: $("layout-note"), frame: $("frame"), banner: $("error-banner")
  };

  var manifest = null;
  var state = { page: 0, style: "", mode: 2, width: "" };
  var loadedPage = -1;
  var notesRequest = 0;
  var navigating = false;

  function styleById(id) {
    for (var i = 0; i < manifest.styles.length; i++) {
      if (manifest.styles[i].id === id) { return manifest.styles[i]; }
    }
    return null;
  }

  function pageIndex(slug) {
    for (var i = 0; i < manifest.pages.length; i++) {
      if (manifest.pages[i].slug === slug) { return i; }
    }
    return -1;
  }

  function showErrors(messages) {
    if (messages.length === 0) {
      els.banner.hidden = true;
      els.banner.textContent = "";
      return;
    }
    els.banner.textContent = messages.join(" ");
    els.banner.hidden = false;
  }

  function parseHash() {
    var params = new URLSearchParams(location.hash.replace(/^#/, ""));
    var errors = [];
    var next = { page: 0, style: "", mode: 2, width: "" };

    var slug = params.get("p");
    if (slug !== null && slug !== "") {
      var idx = pageIndex(slug);
      if (idx === -1) { errors.push('Unknown page "' + slug + '" in URL; showing page 1.'); }
      else { next.page = idx; }
    }
    var styleId = params.get("s");
    if (styleId !== null && styleId !== "") {
      if (styleById(styleId) === null) { errors.push('Unknown style "' + styleId + '" in URL; showing Unstyled.'); }
      else { next.style = styleId; }
    }
    var mode = params.get("m");
    if (mode !== null && mode !== "") {
      if (mode === "1" || mode === "2") { next.mode = Number(mode); }
      else { errors.push('Unknown mode "' + mode + '" in URL; using mode 2.'); }
    }
    var width = params.get("w");
    if (width !== null && width !== "") {
      if (widthKnown(width)) { next.width = width; }
      else { errors.push('Unknown width "' + width + '" in URL; fitting the window.'); }
    }
    return { state: next, errors: errors };
  }

  function widthKnown(value) {
    for (var i = 0; i < els.width.options.length; i++) {
      if (els.width.options[i].value === value) { return true; }
    }
    return false;
  }

  function writeHash() {
    var hash = "#p=" + encodeURIComponent(manifest.pages[state.page].slug) +
      "&s=" + encodeURIComponent(state.style) + "&m=" + state.mode +
      (state.width === "" ? "" : "&w=" + state.width);
    history.replaceState(null, "", hash);
  }

  function addError(message) {
    els.banner.textContent = els.banner.textContent === "" ? message : els.banner.textContent + " " + message;
    els.banner.hidden = false;
  }

  // Point a slot at href. Calls settled(failedHref) once the stylesheet loaded or failed
  // (failedHref is null on success); a slot with no href settles at once.
  function setHref(doc, id, href, settled) {
    var link = doc.getElementById(id);
    if (!link) { settled(null); return false; }
    if (!link.__spWatching) {
      link.__spWatching = true;
      link.__spWaiters = [];
      link.__spResult = undefined;
      var finish = function (failed) {
        link.__spResult = failed;
        var waiters = link.__spWaiters;
        link.__spWaiters = [];
        waiters.forEach(function (w) { w(failed ? link.getAttribute("href") : null); });
      };
      link.addEventListener("load", function () { finish(false); });
      link.addEventListener("error", function () { finish(true); });
    }
    if (!href) {
      link.removeAttribute("href");
      link.__spResult = undefined;
      link.__spWaiters = [];
      settled(null);
      return true;
    }
    if (link.getAttribute("href") === href) {
      // Unchanged href: the browser fires no new event, so reuse the earlier outcome or keep waiting for it.
      if (link.__spResult === undefined) { link.__spWaiters.push(settled); }
      else { settled(link.__spResult ? href : null); }
      return true;
    }
    link.__spResult = undefined;
    link.__spWaiters = [settled];
    link.setAttribute("href", href);
    return true;
  }

  var applyToken = 0;

  function applyToFrame() {
    var token = ++applyToken;
    var doc = els.frame.contentDocument;
    var style = state.style === "" ? null : styleById(state.style);
    var wantsLayout = style !== null && state.mode === 2 && style.hasLayout;
    var layoutHref = wantsLayout ? "/w/styles/" + encodeURIComponent(state.style) + "/layout.css" : "";
    var styleHref = style !== null ? "/w/styles/" + encodeURIComponent(state.style) + "/style.css" : "";
    document.body.setAttribute("data-ready", "false");
    var pending = 2;
    var settled = function (failedHref) {
      if (token !== applyToken) { return; }
      if (failedHref !== null) { addError('Could not load stylesheet "' + failedHref + '".'); }
      pending -= 1;
      if (pending === 0) { document.body.setAttribute("data-ready", "true"); }
    };
    setHref(doc, "sp-style", styleHref, settled);
    setHref(doc, "sp-layout", layoutHref, settled);
    attachKeys(doc);
    var layoutLink = doc.getElementById("sp-layout");
    document.body.setAttribute("data-layout-applied", layoutLink && layoutLink.hasAttribute("href") ? "true" : "false");
  }

  function renderLayoutNote() {
    var style = state.style === "" ? null : styleById(state.style);
    els.layoutNote.hidden = !(style !== null && state.mode === 2 && !style.hasLayout);
  }

  function updateNotes() {
    var token = ++notesRequest;
    els.notes.hidden = true;
    if (state.style === "") { return; }
    var url = "/w/styles/" + encodeURIComponent(state.style) + "/notes.md";
    fetch(url).then(function (resp) {
      // Read the body so the request finishes; an unread body keeps the page from going network-idle.
      return resp.arrayBuffer().then(function () { return resp; });
    }).then(function (resp) {
      if (token === notesRequest && resp.ok) {
        els.notes.setAttribute("href", url);
        els.notes.hidden = false;
      }
    }, function (err) {
      // Only fetch/response failures land here; an exception in the handler above is left to surface.
      if (token === notesRequest) { addError("Could not load notes: " + String(err)); }
    });
  }

  function renderControls() {
    var n = manifest.pages.length;
    els.counter.textContent = (state.page + 1) + " / " + n;
    els.title.textContent = manifest.pages[state.page].title;
    els.prev.disabled = state.page === 0;
    els.next.disabled = state.page === n - 1;
    els.select.value = state.style;
    els.width.value = state.width;
    if (state.width === "") {
      els.frame.removeAttribute("data-width");
      els.frame.style.width = "";
    } else {
      els.frame.setAttribute("data-width", state.width);
      els.frame.style.width = state.width + "px";
    }
    els.mode.textContent = state.mode === 1 ? "Mode 1: style only" : "Mode 2: style + layout";
    els.mode.setAttribute("aria-pressed", state.mode === 2 ? "true" : "false");
    document.body.setAttribute("data-page", manifest.pages[state.page].slug);
    document.body.setAttribute("data-style", state.style);
    document.body.setAttribute("data-mode", String(state.mode));
  }

  function render(pageChanged) {
    renderControls();
    renderLayoutNote();
    if (pageChanged || loadedPage !== state.page) {
      loadedPage = state.page;
      navigating = true;
      document.body.setAttribute("data-ready", "false");
      els.frame.src = "/w/pages/" + encodeURIComponent(manifest.pages[state.page].slug) + "/index.html";
    } else if (!navigating) {
      applyToFrame();
    }
    // While navigating, the load handler applies the then-current state to the new document.
    writeHash();
  }

  function setState(changes) {
    showErrors([]);
    var pageChanged = changes.page !== undefined && changes.page !== state.page;
    var styleChanged = changes.style !== undefined && changes.style !== state.style;
    if (changes.page !== undefined) { state.page = changes.page; }
    if (changes.style !== undefined) { state.style = changes.style; }
    if (changes.mode !== undefined) { state.mode = changes.mode; }
    if (changes.width !== undefined) { state.width = changes.width; }
    render(pageChanged);
    if (styleChanged) { updateNotes(); }
  }

  function go(delta) {
    var target = state.page + delta;
    if (target < 0 || target >= manifest.pages.length) { return; }
    setState({ page: target });
  }

  function onKey(event) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") { return; }
    if (event.ctrlKey || event.metaKey || event.altKey) { return; }
    var target = event.target;
    if (target && (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable)) { return; }
    event.preventDefault();
    go(event.key === "ArrowLeft" ? -1 : 1);
  }

  function attachKeys(doc) {
    if (doc.__spKeysAttached) { return; }
    doc.__spKeysAttached = true;
    doc.addEventListener("keydown", onKey);
  }

  function loadFromHash() {
    var parsed = parseHash();
    showErrors(parsed.errors);
    var styleChanged = parsed.state.style !== state.style;
    var pageChanged = parsed.state.page !== state.page;
    state = parsed.state;
    render(pageChanged);
    if (styleChanged) { updateNotes(); }
  }

  function init(data) {
    manifest = data;
    manifest.styles.forEach(function (s) {
      var option = document.createElement("option");
      option.value = s.id;
      option.textContent = s.name;
      els.select.appendChild(option);
    });

    els.prev.addEventListener("click", function () { go(-1); });
    els.next.addEventListener("click", function () { go(1); });
    els.select.addEventListener("change", function () { setState({ style: els.select.value }); });
    els.width.addEventListener("change", function () { setState({ width: els.width.value }); });
    els.mode.addEventListener("click", function () { setState({ mode: state.mode === 1 ? 2 : 1 }); });
    document.addEventListener("keydown", onKey);
    window.addEventListener("hashchange", loadFromHash);
    els.frame.addEventListener("load", function () {
      // A new document starts without our listener or style; re-apply both.
      navigating = false;
      applyToFrame();
    });

    loadFromHash();
    updateNotes();
  }

  fetch("/manifest.json").then(function (resp) {
    if (!resp.ok) { throw new Error("GET /manifest.json failed: " + resp.status); }
    return resp.json();
  }).then(init).catch(function (err) {
    showErrors([String(err)]);
    throw err;
  });
}());
