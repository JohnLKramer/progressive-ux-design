# Low-level flow template

Mostly-specified state machine of screens. Covers all or almost all system reactions to user actions. Technical edge cases (double-tap, offline, idempotency, accessibility, localization) are out of scope, but listed as such.

```markdown
---
id: <kebab-case>
level: low
title: <flow name>
status: draft
parent: <high-level doc id or "none">
personas: [<persona-id>]        # cite ids only
goal: <one sentence>
success_criteria: [<observable outcomes>]
preconditions: [<what must be true on entry>]
entry_points: [<state ids; add the external source in parentheses>]
source: <original doc path or "free text">
---

# <title>

## Rules
<!-- Business rules that are not a guard on one transition. Values live in parameters. -->

## States
| State | Screen / surface | Conditions on entry | Shows (elements, copy keys) | From beat |
|---|---|---|---|---|
| S1 | | | | B1 |

## Transitions
<!-- Every user action available in a state has a row, including no-ops. -->
| # | From | User action | Guard | System reaction | To |
|---|---|---|---|---|---|
| T1 | S1 | taps X | none | saves Y | S2 |

## Exits
| Exit | Reached from | Hands off to |
|---|---|---|

## External parameters
| Name | Kind | Used in | Value | Rubric |
|---|---|---|---|---|

## Out of scope (technical edge cases)
<!-- List the ones consciously not covered. -->

## Open questions
| # | Question | Assumption made meanwhile | Origin | Resolve in |
|---|---|---|---|---|

## Conversion note
<!-- Converting only: dropped / assumed / missing. -->
```

## Fill rules

- Completeness check before finishing: each state lists every action the screen offers (including close/back); each transition has a `To` that is a state or an Exit; each state is reachable from an entry point or another state.
- Failure the user can see (save fails, rejected input) gets a transition. Failure invisible to the user is out of scope.
- Add a mermaid `stateDiagram-v2` only if asked; the tables are the source of truth.
- "From beat": the `parent` beat id; `none` when parent is none. Don't restate beat text.
- State ids S1.., transition ids T1.., exits E1... Entries may be a state id or an external source.
- Tap-level no-ops: add rows only for actions the screen visibly offers; scrolling and passive gestures are out of scope.
- A source diagram is not carried over; the tables replace it. Mention it in the conversion note.
- Reactions the source left implicit: write the likely one and mark the row `(assumed)`. Each assumed row cites an Open question `Q#` (rows may share one).
- A surface the user sees without opening a screen (notification, email) may be a state.
- Exits: if every path loops back to a home state, write `none (flow loops)`.
- `personas: [unspecified]` when none is implied.
