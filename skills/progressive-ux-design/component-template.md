# Component template

One reusable piece of a screen (header, tab bar, card), standalone, with its own id. Many screens may use it; screens reference it by id and never copy it. Structure only: no visual aesthetics. A component has no states of its own; the screen owns states.

```markdown
---
id: <kebab-case>
kind: component
title: <component name>
status: draft
purpose: <one sentence>
source: <original doc path, or free text>
wireframe: <relative path>      # optional; .html only; omit if inline under ## Wireframe
used_by: [{<screen-id>: [<El-ids>]}]   # informational; may be empty
---

# <title>

## Purpose and success criteria
<!-- What the component is for; observable outcomes. -->

## Rules
<!-- Component-level business rules. Values live in parameters. -->

## Wireframe
<!-- Inline fenced block. Callouts written [El3]. Structure only. -->

## Elements
| Id | Element | Shows | Variation |
|---|---|---|---|
| El1 | | | none |

## Actions
| # | Element | Trigger | Guard | Local result | Exit |
|---|---|---|---|---|---|
| A1 | El1 | tap | none | none | go-back |

## Exits
| Exit | Reached from | Meaning |
|---|---|---|
| go-back | A1 | User leaves the current screen backwards |

## External parameters
| Name | Kind | Used in | Value | Rubric |
|---|---|---|---|---|

## Out of scope
<!-- Consciously not covered (technical edge cases, styling). -->

## Open questions
| # | Question | Assumption made meanwhile | Origin | Resolve in |
|---|---|---|---|---|

## Conversion note
<!-- Converting only: dropped / assumed / missing. -->
```

## Fill rules

- One place: the component's wireframe, elements, actions and exits are written here and nowhere else. A screen cites the component and never copies any of it.
- Ownership: the component owns what its own actions do locally and which Exits it offers. The screen owns where the component sits and which screen states show it. The flow owns where an Exit leads.
- Ids: elements `El1`.., actions `A1`.. Integers only (`El8`, `El9`, never `El8a`). Ids are stable; never renumber on edit. Screens cite actions as `<component-id>.A<n>`.
- No states: don't add `SS#` rows. Differences by screen state go in `Variation` as text (`none` when the element never varies).
- Wireframe, Actions, Exits and parameters follow `screen-template.md` (callouts inside the sketch, structure only, Actions name an Exit or `none`, Exits are named handoffs with no destinations, `| none | | |` if no exits, parameters not inlined in prose). The sketch is inline, or a `wireframe:` path to an `.html` file built by `build-html.md`, which follows the HTML wireframe rule in `screen-template.md` (`data-el`, `data-action`, `data-exit`; ids are component-local; no `data-state`).
- `used_by` is informational, may be empty, and screens win on conflict. Each entry maps a screen id to the bracketed `El` ids of the citing screen, e.g. `used_by: [{game-picks: [El1]}]`.
- A component never cites another component (nesting is out of scope). A region you would nest becomes an element of this component.
- Unknown copy, guards, or behavior become open questions (`Origin`, `Resolve in`), not invention. Copy: refer to a copy key or the source's text.
- Converting? Keep the `## Conversion note`; not converting: omit it.
