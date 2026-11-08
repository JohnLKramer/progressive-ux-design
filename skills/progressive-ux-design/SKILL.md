---
name: progressive-ux-design
description: Use when writing, refining, restructuring, reviewing, or checking user-experience flows for ambiguity, consistency, or completeness, missing pages or behaviors, user personas, single screens, or markdown UI wireframes, or HTML mockups of screens, or when asked how a persona would react to, get bored by, or get stuck in a flow, when given an existing UX flow doc, user description, or market segmentation doc to put into a standard format, or when a flow needs more or less detail than its current layer.
---

# Progressive UX Design

UX is designed in layers. Each layer fixes only what that layer can decide; everything else becomes an **open question** for a later layer. Flow only: no visual aesthetics (built HTML mockups have a greyscale wireframe look with structural layout, no colour, fonts or imagery; see `build-html.md`).

## Route by mode

Load ONLY the file for the chosen mode. Templates are the output shape; fill every slot.

| Mode | Use for | Load |
|---|---|---|
| `high-level-flow-template` | Experience-level journey; judge user impact and sentiment. Not a state machine. | `high-level-flow-template.md` |
| `low-level-flow-template` | Mostly-complete state machine of screens, user actions, system reactions. | `low-level-flow-template.md` |
| `screen-template` | One screen: elements, states, actions, exits; may embed or link a markdown UI wireframe. Used by many flows. | `screen-template.md` |
| `component-template` | One reusable piece of a screen (header, tab bar): elements, actions, exits, markdown sketch. Cited by many screens, written once. | `component-template.md` |
| `build-html` | Build the HTML mockup of one screen or component doc (from its markdown wireframe, "mockdown", when it has one): semantic HTML with the mockdown's layout (wireframe look), bound to the doc by `data-el`, matching the sketch's `[El#]` callouts. | `build-html.md` (also `screen-template.md` or `component-template.md`) |
| `user-persona-template` | Who the user is, for judging flows. | `user-persona-template.md` |
| `evaluate-flows` | Check one flow or a group, with or without screen docs, for ambiguity, consistency, completeness; small fixes, then a survey. | `evaluate-flows.md` (granularity follows each doc's `level`; also load that level's template, `screen-template.md` for a `kind: screen` doc, or `component-template.md` for a `kind: component` doc, when correcting) |
| `simulate-flows` | Persona agents walk a flow; report, recommendations, update. Judges understanding, friction, delight, boredom, goal. | `simulate-flows.md`, then `simulate-report.md` |
| `find-gaps` | Find missing pages (undefined link or action targets) and missing behaviors (state-dependent capabilities the docs leave undefined); interview, then offer to design pages. | `find-gaps.md` (also `screen-template.md` when drafting missing pages) |

**Existing document not in template format** (flow, user description, segmentation, single-screen doc or wireframe): also load `convert-existing-doc.md` (not for find-gaps, which reads raw wireframes as is). It picks the mode unless the user named one.

**Free text, no mode named:** choose by detail in the input. Journey or intent → high-level. Per-screen actions and reactions across connected screens → low-level. Description of people → persona. Description of one screen's elements and states, in isolation → screen. A reusable piece of a screen (header, tab bar) → component. A request for an HTML or mockup page of a screen or component doc → build-html. Asked what is missing or undefined across screens or flows → find-gaps. State the choice in one line in your reply (not in the document).

## Rules for every output

- One layer per document. Link layers with ids (`parent`, `beat`/`state` refs, a flow's `Screen` id, `<screen-id>.A<n>`, a screen's `components` ids and `<component-id>.A<n>`), never by copying content. A piece shared by several screens lives in one component doc.
- Link layers by id; an HTML wireframe binds to its doc by `data-el` only (`build-html.md`). Flows cite elements as `<screen-id>.El<n>`.
- A **parameter** is a number, duration, time, threshold, or member of a fixed set that the product team decides. It goes in the **External parameters** table: `Value` = the source's value, else `unspecified`; `Rubric` = path/URL, else `none yet`. Prose refers to it by name ("the expiry window"), never inlines it. A value the source refers to but doesn't give ("some cutoff", "the morning of") is implied; anything else is not, so don't add it.
- A gap becomes an **Open question**, tagged with `Origin` (`source` if the input asked it, `added` if you found it) and `Resolve in` (`high`, `low`, `persona`, `product`). Don't fill gaps with invention.
- Converting? End the doc with a `## Conversion note` (dropped, assumed, missing). Not converting: omit it.
- Rewrite relative links so they resolve from the output file's own directory.
- Referenced personas or sibling flows that aren't supplied: cite the id only; don't create them.
- Best effort: a thin input still yields a complete template, with gaps listed.

## Locations

Final docs: where the user says, else `ux/<kind>/<id>.md` (`kind` = `flows`, `personas`, `screens`, or `components`). Intermediate drafts only: `.superpowers/work/`.

## Not covered yet

Machine-checkable consistency validators (including screen and component validators; `screen-template.md` and `component-template.md` are checked by prose only): see `docs/status.md`.
