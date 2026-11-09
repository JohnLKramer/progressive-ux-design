# Progressive UX LLM Design Plugin

This is progressive UX design plugins for Claude code. UX design is a layered process. We don't want tpo design user experience
to cover every single obscure edge case up front. So do it in layers.


# Building HTML from a screen doc

The `build-html` mode turns a screen or component doc into an HTML mockup with a greyscale wireframe look. If the doc has a markdown wireframe ("mockdown"), that sketch sets the layout and its `[El3]` callouts set the mapping; the Elements, Actions and Exits tables supply the rest.

The doc and the HTML cross-reference by id:

- `[El3]` in the mockdown, the Elements row `El3`, and `data-el="El3"` in the HTML are the same element.
- `data-action="A2"` and `data-exit="open-profile"` on a node match the Actions and Exits tables.
- Tests and tools find an element with `[data-el="El3"]`.

`build-html` checks this both ways: every row, callout and action has a node, and no node is marked that the doc lacks. Where the sketch and the tables disagree, the doc wins and the difference becomes an Open question. The mode does not convert a bare mockdown with no doc; make the screen doc first (see `convert-existing-doc.md`).


# Style switcher

The `style-switcher` skill previews the same pages in the look of several sites. A workspace holds the pages (`pages/<slug>/index.html`) and the styles (`styles/<id>/`), and a local preview shell lets you flip between them with arrows, a style dropdown and a display mode toggle (style only, or style plus layout).

Run `/style-switcher` and pick one of three modes: `make-stylable` turns a saved page or HTML mockup into a stylable page, `extract-style` turns saved pages or a template zip into a style, and `switch` serves the workspace in your browser. You pass the workspace folder as an argument; the examples here use `.superpowers/workspace/style-switcher/`. A fourth mode, `all`, runs the three in order.

The scripts need Python 3.9 or newer. Playwright is optional: it is only needed for screenshots (`screenshot.py`) and for the acceptance run (`python3 skills/style-switcher/scripts/acceptance.py <workspace> <out-dir>`), which visits every page in every style in both display modes and writes a contact sheet.

Saved pages and zips are untrusted input: scripts never run from them, and screenshots of source pages load them with scripts off and the network blocked.


# design-refine

The `design-refine` skill improves one page of a style-switcher workspace by critique and fix. For each style it runs a bounded loop: render the styled page, have a fresh critic review it against the page's one-sentence intent, fix the most important finding, check the fix, and keep it only if a before/after comparison says it is not worse.

Run `/design-refine <workspace> <slug> <style...>`, optionally with `--doc` (the screen doc the page came from), `--max-iterations` (default 5) and `--bar` (default `P2`; findings below it are reported, not fixed). With more than one style the loop runs once per style.

Style-only findings are fixed in that style's CSS. Structural findings (hierarchy, grouping, markup) are fixed in the screen doc or the page's own HTML, so every style inherits them. Structural fixes are applied automatically behind gates: the page's markers, the page and style validators, a check that only allowed files changed, and a render in a second style. A fix that fails a gate or makes the page worse is reverted. A finding is retried once with a different approach, then given up on. Findings that need a product decision go to a needs-you list instead.

Each run writes a log folder, `<workspace>/.design-refine/<slug>--<style>/`, with the ledger, before and after screenshots per iteration and a `report.md`. A rerun needs a fresh folder: remove or rename the old one.

It needs Python 3.9 or newer and Playwright for Python with its Chromium browser, which renders the screenshots the critic reviews.
