# Building an HTML mockup

Input: one `kind: screen` or `kind: component` doc (and its markdown wireframe, if any). Output: one `.html` file bound to the doc, and the doc's `wireframe:` path set. The doc is the source of truth; the HTML is derived from it and may be rebuilt when the doc changes.

## The file

- **Unstyled semantic HTML:** real controls (`button`, `nav`, `input`, `a`) in the wireframe's region order, browser-default look. No `style`, `<style>`, color, font, spacing, or imagery; avatars and images are labelled boxes or text. No script, no handlers, no id-overlay toggle.
- **Copy** comes from copy keys or the doc and wireframe as written, typos included. Never write new copy; a placeholder stays a placeholder.
- **One state per file.** Default state SS1 unless the user names another. Screens: `<main data-screen="<id>" data-state="SS1">`. Components: `<section data-component="<id>">`, no state.
- **Binding:** follow the HTML wireframe rule in `screen-template.md` (`data-el`, `data-action`, `data-exit`; never `id="El#"`). Container nodes that are not elements carry no marks. An element made of several parts (a tab bar of four tabs) puts `data-el` on the one node that wraps all its parts (`nav`); its parts carry only `data-action` or nothing.
- **Tags follow role:** `button` for anything with an Action, `a` for navigation, a heading for a headline, text otherwise. A chip or label with no Action is plain text, not a button.
- **Tests and tools** target elements as `[data-el="El3"]`, the same id as the Elements row, so a requirement on an element maps straight to a UI test. Never by tag, class, or text.
- **Header comment:** one line naming the doc.
- **Location:** where the user says, else `ux/mockups/<id>.html` (`<id>-<state>.html` for a non-default state).

## Procedure

1. Read the doc. List every Elements row, action, and exit to mark.
2. Write the HTML. Draw only what the doc shows or implies; a doc gap stays a gap (an Open question, `Origin: added`, `Resolve in: low`), not invented content, e.g. which tab is selected when the doc does not say.
3. Set the doc's `wireframe:` to the relative path (resolving from the doc's own directory). Keep an existing inline sketch; the doc wins on conflict. The only doc edits are that front-matter line and an Open question if step 2 found a gap: no pointer sentence, no new section, no Conversion note change, and `source:` is left as written.
4. Check by searching the file for `data-el=`, `data-action=`, `data-exit=`: each Elements row once; nothing extra; every action and exit value in the tables. Fix, then report in two lines: the file path, and any gaps raised.
