---
name: style-switcher
description: Use when previewing a UX design, HTML mockup, or saved web page in the look of other sites, restyling pages to compare styles, extracting a style from saved pages or a zip, or flipping between styles in a browser.
---

# Style Switcher

Preview unstyled pages in many looks. A workspace holds `pages/<slug>/index.html` and `styles/<id>/`; a local preview shell flips between them.

The switcher's **display mode** is 1 (style only) or 2 (style plus layout); it is separate from the skill modes below.

## Route by mode

Load ONLY the file for the chosen mode.

| Mode | Use for | Load |
|---|---|---|
| `make-stylable` | Turn a saved web page or an HTML mockup into a stylable page in a workspace: roles and wrappers, content untouched. | `make-stylable.md` |
| `extract-style` | Turn saved pages of a site, or a template zip, into a reusable style in a workspace: tokens, CSS, optional layout, assets. | `extract-style.md` |
| `switch` | Serve a workspace in a browser: arrows between pages, a style dropdown, a display mode toggle. | `switch.md` |
| `all` | Run `make-stylable` on the pages, then `extract-style` on the sources, then `switch`. | Load each mode's file in that order, one at a time, finishing each before the next. |

## Rules for every output

- Example data is read-only. Never edit it.
- Outputs go to the workspace folder.
- A stylable page has no `script`, no `style` element, no inline `style`, no `on*` handlers, no remote assets, and two `<head>` slots with no `href` attribute: `<link id="sp-style" rel="stylesheet">` and `<link id="sp-layout" rel="stylesheet">`.
- Roles come only from `role-vocabulary.md`. Never invent one. The only other attribute a page may add is `hidden`, within the limits in `role-vocabulary.md`.
- Emphasis: a style highlights the page's content, not just its chrome. Lead figures, headings and status badges carry the brand's accent and status colors; `extract-style.md` says how.
- Failures stop loudly with the output shown. The one soft case is display mode 2 on a style without `layout.css`: the shell shows the style alone and says so.

## Untrusted inputs

- Unpack zips into a new, empty directory.
- Pass paths as arguments, never inside a shell string.
- Never run anything from an archive.
- Never feed raw HTML to the model. The exceptions are a screenshot of a source page taken by `screenshot.py`, which loads it with scripts off and the network blocked and returns only a picture, and the sanitized page that `strip_page.py` writes, which `make-stylable` prints and edits with scripted exact-match edits.

## Running scripts

`<skill-dir>` is the directory that contains this `SKILL.md`; every script path below is relative to it. Scripts live in `<skill-dir>/scripts/`. `screenshot.py` and `acceptance.py` run as plain `python3 <skill-dir>/scripts/screenshot.py`, because they import Playwright and `-I` hides it. Every other script runs as `python3 -I <skill-dir>/scripts/<script>.py`. Always call a script through its interpreter, never by bare path.
