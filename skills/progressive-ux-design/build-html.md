# Building an HTML mockup

Input: one `kind: screen` or `kind: component` doc (and its markdown wireframe, "mockdown", if any; inline under `## Wireframe` or at a `wireframe:` `.md` path). Output: one `.html` file bound to the doc, and the doc's `wireframe:` path set. The doc is the source of truth; the HTML is derived from it and may be rebuilt when the doc changes.

## The file

- **Unstyled semantic HTML:** real controls (`button`, `nav`, `input`, `a`) in the wireframe's region order, browser-default look. No `style`, `<style>`, color, font, spacing, or imagery; avatars and images are labelled boxes or text. No script, no handlers, no id-overlay toggle.
- **Copy** comes from copy keys or the doc and wireframe as written, typos included. Never write new copy; a placeholder stays a placeholder.
- **One state per file.** Default state SS1 unless the user names another. Screens: `<main data-screen="<id>" data-state="SS1">`. Components: `<section data-component="<id>">`, no state.
- **Binding:** follow the HTML wireframe rule in `screen-template.md` (`data-el`, `data-action`, `data-exit`; never `id="El#"`). Container nodes that are not elements carry no marks; an element may sit inside another element. An element made of several parts (a tab bar of four tabs) puts `data-el` on the one node that wraps all its parts (`nav`); its parts carry only `data-action` or nothing.
- **Tags follow role:** `button` for anything with an Action, `a` for navigation, a heading for a headline, text otherwise. A chip or label with no Action is plain text, not a button.
- **Tests and tools** target elements as `[data-el="El3"]`, the same id as the Elements row, so a requirement on an element maps straight to a UI test. Never by tag, class, or text.
- **Header comment:** one line naming the doc.
- **Location:** where the user says, else `ux/mockups/<id>.html` (`<id>-<state>.html` for a non-default state).

## From mockdown

The mockdown gives layout; its `[El#]` callouts give the mapping. The cross-reference runs through the element id, never through position or text:

- Each `[El3]` callout in the sketch becomes one node `data-el="El3"` in the same region and order. A `[El2 component: <id>]` slot becomes one node `data-el="El2"`, drawn from the component's Elements and Actions; inside it only actions are marked, as `data-action="<component-id>.A<n>"` (and `data-exit`), never `data-el`.
- A callout ending `, repeats` becomes one node per `## Variants` row of the cited component, each with `data-el` and `data-variant="V<n>"`, in the region the sketch shows, drawn with the variant's example data. Inside an instance, a node that triggers a component action carries `data-action="<component-id>.A<n>"` (and `data-exit`) from the component's Actions table; nothing inside is `data-el`.
- A sketch with no callouts has no mapping. Add the `[El#]` marks to the inline sketch first, following `screen-template.md` (change nothing else; a linked `.md` is left untouched and the marks go in a key under `## Wireframe`). Match sketch pieces to Elements rows by the row's `Element` and `Shows` text. A piece you cannot match with confidence is an Open question, not a guess.
- A piece in the sketch with no Elements row, or an Elements row with no piece in the sketch (other than `not drawn`), is a doc gap: leave it out of the HTML and raise an Open question.
- Actions: a node that triggers a row of the Actions table gets `data-action` (and `data-exit`) from that row's `Element`, not from how the sketch looks.

## Procedure

1. Read the doc and its mockdown. List every Elements row, callout, action, and exit to mark (see From mockdown).
2. Write the HTML. Draw only what the doc shows or implies; a doc gap stays a gap (an Open question, `Origin: added`, `Resolve in: low`), not invented content, e.g. which tab is selected when the doc does not say.
3. Set the doc's `wireframe:` to the relative path (resolving from the doc's own directory). Keep an existing inline sketch; the doc wins on conflict. The only doc edits are that front-matter line and an Open question if step 2 found a gap: no pointer sentence, no new section, no Conversion note change, and `source:` is left as written.
4. Check both directions by searching the file for `data-el=`, `data-action=`, `data-exit=`: each Elements row once, or for a repeats row once per Variants row with a matching `data-variant`; no `data-el` the table lacks; every `[El#]` callout has its node(s) and every node has its callout; every action and exit value is in the tables, and every Actions row with an Element in this file has a node. Fix, then report in two lines: the file path, and any gaps raised.
