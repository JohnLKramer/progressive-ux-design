# Evaluating flows

Input: one flow doc or a group, optionally with screen docs. Each doc's `level:` front matter sets its granularity. A doc with `kind: screen` is a screen: evaluate it with the screen lens below; it has no `level` and never triggers the convert question. A flow doc without `level:` front matter: ask whether to convert it to high or low (`convert-existing-doc.md`), then evaluate the result. Missing template slots or formatting in a doc that has `level:` are not findings; leave them.

Three lenses:

| Lens | High-level doc | Low-level doc |
|---|---|---|
| **Ambiguity**: a term, beat, or reaction that reads two ways | Concepts, terms, who/what a beat refers to | Which state, guard, or reaction a row means |
| **Consistency**: two statements that can't both hold | Beats vs rules, goal vs journey, doc vs doc | Transitions vs states, guards vs rules, `parent` beats, doc vs doc |
| **Completeness** | Intention-level gaps only (a goal with no path, a decline with no outcome) | Every offered action has a transition with a reaction and a `To` |

Screen docs (`kind: screen`):

| Lens | Screen doc |
|---|---|
| **Ambiguity** | An element or state that reads two ways (a gap already in Open questions is not raised again) |
| **Consistency** | Callouts vs Elements, `In states` vs States rows, Actions vs Exits; a `wireframe:` path that does not resolve |
| **Completeness** | Required states (default, loading, empty, error) present or `n/a, because ...`; every action has a trigger and a local result; every Exit declared |

Cross-doc checks when a flow and a screen are both given. Each failure is a cross-doc conflict in the summary:
- Every flow `Screen` id resolves to a screen doc.
- Every `<screen-id>.A<n>` a flow cites exists on that screen.
- Every Exit a flow uses exists on that screen.
- A screen's `used_by` matches the flows that reference it. An empty `used_by` is not a finding.
- A screen action's `Local result` does not contradict the flow transition's reaction (screen says "stays", flow says "goes to S3").

The screen owns local behavior (stays, opens a modal, saves). The flow owns the journey (where an exit leads, which state follows).

Technical gaps (network, exceptions, double-tap, offline) are out of scope at every level; never raise them. Formal precision is not the bar: stop at "a designer would not be misled".

## Procedure

1. **Evaluate** silently, all three lenses, every doc.
2. **Small corrections.** Apply one only when the doc itself supports exactly one reading (a dangling id, a term the doc defines used differently, a duplicate question, a return transition whose target the doc's own state text fixes). If fixing means choosing what the user wants, it is a question, not a correction. List each correction in the summary.
3. **Summary**, in this shape and nothing more:
   - One line per doc: `<id> (<level>): <n> ambiguity, <n> consistency, <n> completeness` (single-doc concerns only)
   - Group-wide ambiguity and cross-doc conflicts: one count each
   - Corrections made: one line each
   - Ask: "Address the ambiguity and consistency concerns now?" Completeness is not mentioned yet.
4. **If yes: survey, ambiguity then consistency.** Order:
   1. Group-wide ambiguity (terms or concepts unclear across the group)
   2. Per-flow ambiguity
   3. Conflicts between two flows
   4. Inconsistencies inside one flow
5. **Apply** the answers as corrections, writing the docs now. Each **skipped** question becomes an Open question row (`Origin: added`, `Resolve in` set).
6. **Ask**: "Address the completeness concerns now?" If yes, survey with the same rules, apply, record skips. If no, record them as Open questions.
7. Rewrite the docs after each apply step, same ids and paths unless the user says otherwise.

## Survey rules

Use the interactive question tool: one call per step-4 group, at most 4 questions per call, at most 3 readings plus Skip per question.

- Skip empty groups; a single doc has no group-wide or cross-flow step.
- A skipped question's `Resolve in` is the layer that must answer it (`high`, `low`, `persona`, `product`).
- Every question starts with `Flow: <id>` (or `Flows: <id> vs <id>`; `Group` for group-wide).
- State the concern in one sentence, quoting the beat/state/transition ids involved.
- Options: the plausible readings, then **Skip (decide later)**. Always present, always last.
- Screen-vs-flow conflict: options are "Change the screen", "Change the flow", then Skip. Append "(owner by the rule)" to the side that owns the contested thing (what an action does on the screen, including whether the user stays or leaves, and which actions exist: screen; which state follows an Exit: flow). Say nothing else about which is right; never guess intent. A skipped one becomes an Open question with `Resolve in: low`, recorded on the flow.
- A question never contains a recommendation that presumes intent. Offer readings; the user picks.
- No question on a lens or topic the user declined.
