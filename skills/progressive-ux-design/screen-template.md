# Screen template

One screen, standalone, with its own id. Many flows may use it; flows reference it by id and never copy it. Structure only: no visual aesthetics.

```markdown
---
id: <kebab-case>
kind: screen
title: <screen name>
status: draft
purpose: <one sentence>
route: <route or surface>
personas: [<persona-id>]        # cite ids only
used_by: [<flow-id (state ids)>]   # informational; may be empty
wireframe: <relative path>      # optional; omit if inline under ## Wireframe
---

# <title>

## Purpose and success criteria
<!-- What the screen is for; observable outcomes. -->

## Rules
<!-- Screen-level business rules. Values live in parameters. -->

## Wireframe
<!-- Inline fenced block, or the front-matter path. Callouts written [El3]. -->

## Elements
| Id | Element | Shows | In states |
|---|---|---|---|
| El1 | | | SS1 |

## States
| State | Entry condition | Elements that change | Wireframe |
|---|---|---|---|
| SS1 default | | | |
| SS2 loading | n/a, because <reason> | | |
| SS3 empty | | | |
| SS4 error | | | |

## Actions
| # | Element | Trigger | Guard | Local result | Exit |
|---|---|---|---|---|---|
| A1 | El1 | tap | none | stays; updates El2 | none |
| A2 | El2 | tap | none | none | open-profile |

## Exits
| Exit | Reached from | Meaning |
|---|---|---|
| open-profile | A2 | User leaves to see a profile |

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

- Ownership: the screen owns local behavior (stays, opens a modal, saves); the flow owns the journey (where an exit leads).
- Ids: elements `El1`.., actions `A1`.., screen states `SS1`.. (never `S1`, which flows use). Integers only: sub-parts get their own number (`El8`, `El9`), never `El8a`. Ids are stable; never renumber on edit.
- States: loading, empty, and error each get a state row or an n/a row, which keeps its id: `| SS2 loading | n/a, because <reason> | | |` (reason in `Entry condition`, other cells empty). If the source is silent on one (e.g. wireframe only), write `n/a, because source does not show it` AND add an Open question (`Origin: added`, `Resolve in: low`). A state that overlays others (alert, banner, narrow viewport) says which in `Entry condition` (`overlays SS1, SS3`). Every element appears in at least one state's `In states`.
- Wireframe: either an inline fenced block under `## Wireframe` or a relative path in front matter `wireframe:` (rewrite it to resolve from the output file). Callouts are written `[El3]` inside the wireframe itself, never only in a legend below it; every callout resolves to the Elements table, and every element has a callout, except an element that exists only in a state the wireframe doesn't draw (e.g. an error banner): mark it `not drawn` in the key or the States `Wireframe` column. A source wireframe with no callouts: add `[El#]` marks to the inline copy, changing nothing else; if it is linked, leave the file untouched and list the marks as a key under `## Wireframe`. Source with no wireframe: sketch regions and slots from the described layout only, and say so in the conversion note, or for a non-conversion in a one-line comment under `## Wireframe`. If no layout is described, sketch nothing: leave the section as `none` and add an Open question (`Origin: added`, `Resolve in: low`). Per-state wireframes: name them in the States `Wireframe` column, else `same`.
- Wireframes carry structure only: regions, order, and content slots. No colors, fonts, spacing values, or imagery. A source wireframe is kept or linked, not redrawn.
- Actions: screen-local results only. The Actions table never names a destination screen or flow state; it names an `Exit` (kebab-case, e.g. `open-profile`) or `none`. `Element` is an element id; use `screen` for triggers with no element (arrival, timer). Each offered action has a trigger and a local result, including close/back. An action the source implies but does not show: write the row, mark the result `(assumed)`, cite an Open question `Q#`. One it does not imply: open question only, no row. Scrolling and passive gestures are out of scope.
- Exits: named handoffs, no destinations; flows resolve them. If the screen offers none, write one row `| none | | |`. Several actions sharing one exit are listed together in `Reached from` (`A2, A5`). Every Exit named in Actions is a row here, and every row here is named in Actions.
- `used_by` is informational, may be empty, and flows win on conflict.
- Unknown states, copy, guards, or behavior become open questions (`Origin`, `Resolve in`), not invention. Don't add states the source doesn't show or imply; list the unknown state in the question instead.
- Copy: refer to a copy key or the source's text; don't write new copy.
- Parameters: values the product team decides (limits, counts, durations) go in External parameters; prose uses the name.
- `personas: [unspecified]` when none is implied.
- Converting? Keep the `## Conversion note`; not converting: omit it.
