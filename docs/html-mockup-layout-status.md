# Status: HTML mockup layout fix (PR #13)

PR: https://github.com/JohnLKramer/progressive-ux-design/pull/13 (branch `cursor/html-mockup-layout`)
Source issue: JohnLKramer/pc-ux-design PR 9, `brainstorming/skill-fixes/html-mockups-need-layout.md` and `picks-home-unstyled.png`.

## Problem

`build-html` said "unstyled, browser-default look, no `style`". Agents read that as "no layout", so a Picks Home mockdown (header bar, 3-column card grid, corner picker, bordered opponent box, CTA tile) rendered as one left-aligned column of blue underlined links.

## What changed (all under `skills/progressive-ux-design/` unless noted)

- `SKILL.md`, `build-html.md`, `README.md`: "unstyled" became "structure only": greyscale wireframe look, system font, one border colour. Still banned: colour, custom fonts, imagery, shadows, rounded decoration, animation, brand, breakpoints, script.
- New `wireframe.css`: shared stylesheet, copied beside each output file and linked relatively. No `style=` and no `<style>`.
- `build-html.md`: fixed `wf-*` class vocabulary (`wf-bar`, `wf-row`, `wf-row-center`, `wf-row-end`, `wf-chip-row`, `wf-col`, `wf-grid-2/3/4`, `wf-card`, `wf-tile`, `wf-box`, `wf-corner-tl/tr/bl/br`). Layout wrappers carry no `data-*`; tests still use `data-el`, `data-action`, `data-exit`, `data-variant` only.
- `build-html.md`: new "Layout from mockdown" table and rules (count rows and columns, keep relative position and grouping, repeats keep their drawn cells, ambiguous layout is an Open question).
- `build-html.md`: block links in cards inherit text colour, no underline; cards have a visible border.
- `build-html.md`: new procedure step 5, render at about 1440px and compare columns, corners, boxes and item order against the mockdown. Component files also use the wireframe look.

## Not done / unverified

- No baseline-and-GREEN runs per `writing-skills` and `docs/status.md`. The PR's screenshot was treated as the baseline.
- No page built or rendered; `wireframe.css` is untested, including `:has()` padding for corner slots and the "centred" nav in `wf-bar` (flex `space-between`, only approximately centred).
- `screen-template.md`, `component-template.md` and `simulate-flows.md` unchanged (no "unstyled" wording found).
- `docs/status.md` not updated.

## Open points

- Stylesheet placement: chose copy beside each output file; the alternative is a path the user sets once.
- `simulate-flows`: whether personas should get a screenshot of the rendered screen where the host can make one.
- `style-switcher`: stylable pages forbid extra stylesheet links beyond `sp-style` and `sp-layout`. `make-stylable` may need to strip or tolerate the `wireframe.css` link. Not checked.

## Next steps

1. Rebuild Picks Home and `site-header` in the consumer repo (Picks Cover) with this branch's skill.
2. Check the 8 acceptance points from the source file: header bar on one line; chips in one row; 3-column bordered cards with CTA tile in row 2 middle; picker top-right on each card; `@ Ravens -3.5` in a bordered box; CTA tile has a small grid of league buttons; card text not blue or underlined; markers unchanged (diff `data-el`, `data-action`, `data-exit`, `data-variant` before and after).
3. Fix `wireframe.css` and the wording from what the render shows; add GREEN notes to `docs/status.md`.
4. Check `style-switcher` `make-stylable` against the new `<link>`.
