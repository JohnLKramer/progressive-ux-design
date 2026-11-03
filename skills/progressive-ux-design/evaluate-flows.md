# Evaluating flows

Input: one flow doc or a group, optionally with screen docs. Each doc's `level:` front matter sets its granularity. A doc with `kind: screen` is a screen: evaluate it with the screen lens below; it has no `level` and never triggers the convert question. A doc with `kind: component` is a component: evaluate it with the component lens below; it has no `level` or states. A flow doc without `level:` front matter: ask whether to convert it to high or low (`convert-existing-doc.md`), then evaluate the result. Missing template slots or formatting in a doc that has `level:`, or in a `kind: screen` doc (apart from the required state rows), are not findings; leave them.

Three lenses:

| Lens | High-level doc | Low-level doc |
|---|---|---|
| **Ambiguity**: a term, beat, or reaction that reads two ways | Concepts, terms, who/what a beat refers to | Which state, guard, or reaction a row means |
| **Consistency**: two statements that can't both hold | Beats vs rules, goal vs journey, doc vs doc | Transitions vs states, guards vs rules, `parent` beats, doc vs doc |
| **Completeness** | Intention-level gaps only (a goal with no path, a decline with no outcome) | Every offered action has a transition with a reaction and a `To` |

Screen docs (`kind: screen`):

| Lens | Screen doc |
|---|---|
| **Ambiguity** | An element or state that reads two ways |
| **Consistency** | Callouts vs Elements, `In states` vs States rows, Actions vs Exits; every parameter used is in the parameters table; a `wireframe:` path that does not resolve |
| **Completeness** | Required states (default, loading, empty, error) present or `n/a, because ...`; every element appears in at least one state; every action has a trigger and a local result; every Exit declared |

Component docs (`kind: component`):

| Lens | Component doc |
|---|---|
| **Ambiguity** | An element or action that reads two ways |
| **Consistency** | Callouts vs Elements, Actions vs Exits, every parameter used is in the parameters table; a `used_by` or action citing another component (nesting is out of scope) |
| **Completeness** | Every action has a trigger and a local result; every Exit declared; no state rows (screens own states) |

Cross-doc checks when a screen and a component are both given. Each failure is a cross-doc conflict in the summary:
- Every component id in a screen's `components` or Elements `component:` rows resolves to a supplied component doc; an id whose doc is not supplied is not checked.
- Every `<component-id>.A<n>` a screen cites exists on that component.
- Every component Exit appears in the screen's Exits table with `Reached from` naming the cited action, and no screen Exit names a component action that doesn't exist.
- The screen does not redefine a component's element or action (its own copy of the header's elements, or a screen row that contradicts the component's `Local result` without being marked as an override).
- A component's `used_by` is compared only against the supplied screens, with the same safe rule as screens: add citing screens, never remove entries for unsupplied ones; a mismatch is a small correction (screens win).

The component owns what its own elements and actions do and which Exits it offers. The screen owns where the component sits and which states show it.

Cross-doc checks when a flow and a screen are both given. Each failure is a cross-doc conflict in the summary:
- Every flow `Screen` id resolves to a supplied screen doc; an id whose doc is not supplied is not checked (cite the id only).
- Every `<screen-id>.A<n>` a flow cites exists on that screen.
- Every Exit a flow uses exists on that screen. A flow names the Exit in `System reaction` as `via <exit-name>`; a flow that names none uses the cited action's `Exit`.
- A screen's `used_by` is compared only against the supplied flows. Add any supplied flow that cites the screen; never remove an entry naming a flow that was not supplied. An empty `used_by` with no supplied flow citing the screen is not a finding. A mismatch is a small correction (flows win): fix `used_by`, not a question.
- A screen action's `Local result` does not contradict the flow transition's reaction (screen says "stays", flow says "goes to S3").

The screen owns local behavior (stays, opens a modal, saves). The flow owns the journey (where an exit leads, which state follows).

A gap already in an Open questions table is not raised again, in any doc or lens. It counts as covered only if the existing question names the same element, state, or transition. A contradiction between two docs is not a gap; an Open question on one side does not suppress it.

Technical gaps (network, exceptions, double-tap, offline) are out of scope at every level; never raise them. Formal precision is not the bar: stop at "a designer would not be misled".

## Procedure

1. **Evaluate** silently, all three lenses, every doc.
2. **Small corrections.** Apply one only when the doc itself supports exactly one reading (a dangling id, a term the doc defines used differently, a duplicate question, a return transition whose target the doc's own state text fixes, a screen `used_by` that disagrees with the flows citing it). If fixing means choosing what the user wants, it is a question, not a correction. List each correction in the summary.
3. **Summary**, in this shape and nothing more:
   - One line per doc: `<id> (<level>): <n> ambiguity, <n> consistency, <n> completeness` (single-doc concerns only); a screen doc is `<id> (screen)`
   - Group-wide ambiguity and cross-doc conflicts: one count each
   - Corrections made: one line each
   - Ask: "Address the ambiguity and consistency concerns now?" Completeness is not mentioned yet.
4. **If yes: survey, ambiguity then consistency.** Order:
   1. Group-wide ambiguity (terms or concepts unclear across the group)
   2. Per-flow or per-screen ambiguity
   3. Conflicts between two flows, or between a screen and a flow
   4. Inconsistencies inside one flow or one screen
5. **Apply** the answers as corrections, writing the docs now. Each **skipped** question becomes an Open question row (`Origin: added`, `Resolve in` set).
6. **Ask**: "Address the completeness concerns now?" If yes, survey with the same rules, apply, record skips. If no, record them as Open questions.
7. Rewrite the docs after each apply step, same ids and paths unless the user says otherwise.

## Survey rules

Use the interactive question tool: one call per step-4 group, at most 4 questions per call, at most 3 readings plus Skip per question.

- Skip empty groups; a single doc has no group-wide or cross-flow step.
- A skipped question's `Resolve in` is the layer that must answer it (`high`, `low`, `persona`, `product`).
- Every question starts with `Flow: <id>` (or `Flows: <id> vs <id>`; `Flow: <id> vs Screen: <id>` for a screen-vs-flow conflict; `Screen: <id>` for a screen alone; `Group` for group-wide).
- State the concern in one sentence, quoting the beat/state/transition ids involved.
- Options: the plausible readings, then **Skip (decide later)**. Always present, always last.
- Screen-vs-component conflict: options are "Change the screen", "Change the component", then Skip, with "(owner by the rule)" on the component for what its actions do and which Exits it offers, and on the screen for placement and states. Prefix `Screen: <id> vs Component: <id>`. A skipped one becomes an Open question on the screen with `Resolve in: low`.
- Screen-vs-flow conflict: options are "Change the screen", "Change the flow", then Skip. Append "(owner by the rule)" to the side that owns the contested thing (what an action does on the screen, including whether the user stays or leaves, and which actions exist and which Exits exist: screen; where an Exit leads and which state follows: flow). An item with no owner under this rule gets no mark. Say nothing else about which is right; never guess intent. A skipped one becomes an Open question with `Resolve in: low`, recorded on the flow; it is asked again on a later run, on purpose (it is a contradiction, not a covered gap).
- A question never contains a recommendation that presumes intent. Offer readings; the user picks.
- No question on a lens or topic the user declined.
