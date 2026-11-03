# Component template design

Date: 2026-11-03
Status: approved in chat.

## Intent

A shared UI piece (a header, a tab bar) must live in one place. Today each screen embeds its own wireframe, so a shared header is copied into every screen and drifts. Components extend the existing rule one level down: flows cite screens by id and never copy them; screens cite components by id and never copy them.

## Design

New doc kind `kind: component`, template `component-template.md`.

- Front matter: `id`, `kind: component`, `title`, `status`, `purpose`, `source`, `used_by` (informational; screens win on conflict).
- Sections: Purpose and success criteria, Rules, Wireframe (structure only, `[El#]` callouts), Elements, Actions, Exits, External parameters, Out of scope, Open questions, Conversion note.
- No states of its own. Screens own states. The component can't know a screen's `SS#` ids, so its Elements table has a `Variation` column (text, e.g. "back button hidden on the first screen") instead of `In states`. The citing screen's Elements row gives the states.
- Ids `El#`, `A#` are per doc and stable.

Screens:
- A screen cites a component with an Elements row: `El2 | component: <id> | ... | SS1, SS2`, and lists it in front-matter `components: [<id>]`.
- The screen wireframe marks the slot `[El2 component: <id>]`; it never copies the component's sketch or elements.
- A flow or screen cites a component action as `<component-id>.A<n>`. The screen's Actions table does not repeat component actions; it adds a row only to override a local result.
- Component exits propagate: a screen's Exits table lists them with `Reached from` = `<component-id>.A<n>`.

Router, convert, evaluate:
- SKILL.md: new mode row, ids rule, output path `ux/components/<id>.md`.
- convert-existing-doc.md: a region repeated across several screens may be proposed as a component; ask, never extract unasked.
- evaluate-flows.md: a component lens plus cross-doc checks (cited ids resolve, cited actions exist, exits match, no element redefined on the screen, `used_by` reconciled). A screen-vs-component conflict is owned by the component.

## Out of scope

Nested components, parameterized variants, validators.

## Testing

Prose-checked like the screen template. A component doc plus a clean screen and a conflicting screen, run through evaluate.
