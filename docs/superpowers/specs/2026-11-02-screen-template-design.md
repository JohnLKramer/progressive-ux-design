# Screen template design

Date: 2026-11-02
Status: draft, awaiting review

## Intent

Flow docs suit journeys you want to optimize. They suit utility screens poorly. A screen can be used by several flows. We need a template for one screen that:

- stands alone, with its own id
- can embed or link a markdown UI (an ASCII wireframe, like `.superpowers/example/screens/game-picks.md`)
- is referenced by flows rather than copied into them

Structure only, no visual aesthetics, matching the rest of `progressive-ux-design`. A screen decides what that layer can decide. Everything else is an open question.

## Research summary

Public UX-spec templates agree on: purpose and success criterion, layout, components, a state matrix (loading, empty, error, disabled), interactions as trigger / feedback / result, content rules, testable acceptance criteria. Missing states is the most common gap. There is no established standard for text-based screen specs. Small projects such as Markdown-UI DSL (`.ui.md` plus YAML front matter) exist. Google's DESIGN.md covers design tokens, not screens.

Sources:
- https://skills.sh/abhsin/designskills/ux-specification
- https://playbooks.com/skills/mae616/design-skills/ui-designer
- https://skillselion.com/skills/rshankras/claude-code-apple-skills/ux-spec
- https://github.com/MegaByteMark/markdown-ui-dsl
- https://pasqualepillitteri.it/en/news/1251/google-stitch-open-source-design-md-spec-2026

## Decisions

1. **Approach:** one new mode, `screen-template`, one doc per screen, fixed section order. Rejected: a third `level` of the flow template (forces a flow shape onto a non-flow), and two files per screen (drift).
2. **Ownership:** the screen owns local behavior (stays, opens a modal, saves). The flow owns the journey (where an exit leads). Conflicts are found by evaluation, which offers a fix.
3. **Wireframe:** either an inline fenced markdown UI or a path to an external file. The evaluator treats both the same.

## Template

Front matter: `id`, `kind: screen`, `title`, `status`, `purpose` (one sentence), `route` or surface, `personas` (ids only), `used_by` (flow ids and states; informational, flows are the source of truth).

Body, fixed order:

1. **Purpose and success criteria.**
2. **Rules.** Screen-level business rules. Values live in parameters.
3. **Wireframe(s).** Inline block or `wireframe: <path>`. Elements carry stable ids (`E1`...). The wireframe marks them with callouts.
4. **Elements.** id, element, shows (data or copy key), states it appears in.
5. **States.** Matrix: state, entry condition, elements that change, wireframe used. Default, loading, empty, error each get a row or an explicit "n/a, because ...".
6. **Actions.** element, trigger, guard, local result, `Exit` (an outward id).
7. **Exits.** Named handoffs (e.g. `open-profile`). No destinations; flows resolve them.
8. **External parameters, Out of scope, Open questions.** Same shape as the flow templates. A gap becomes an open question with `Origin` and `Resolve in`. No invention.

## Integration

- **Flow link:** the low-level flow `States` table gains an optional `screen: <screen-id>` field. The flow keeps its own "Shows" column for journey-specific variation. A flow transition names a screen action by element id (`E4 tap`). The screen's `Exit` supplies the handoff. The flow decides the destination state.
- **Router:** add `screen-template` to `SKILL.md`, with `screen-template.md` (template and fill rules). Screens go in `ux/screens/<id>.md`, so `kind` gains `screens`. Free text describing one screen's elements and states routes here.
- **Conversion:** `convert-existing-doc.md` gains a case for existing wireframes. Link or embed the wireframe, assign element ids, infer a states table, mark unknowns as open questions with `Origin: added`. Do not invent states.

## Evaluation (extends `evaluate-flows.md`)

Single screen:
- every element appears in at least one state
- every wireframe callout resolves to an element id, and the reverse
- loading, empty, error each have a row or "n/a, because ..."
- every action has a trigger and a local result; every `Exit` is declared
- every parameter used is in the parameters table

Screen and flow together:
- every flow `screen:` reference resolves
- every action a flow takes from a state matches an action on that screen; every `Exit` a flow uses exists
- screen `used_by` agrees with the flows that reference it
- a screen's local result does not contradict a flow's reaction (e.g. screen says "stays", flow says "goes to S2")

For each mismatch the evaluator reports it and offers a fix, naming the recommended side by the ownership rule.

## Testing

Same method as the existing skill: baseline agents without the skill, then GREEN with it. Inputs: `game-picks.md` converted to a screen doc; the Stash flow's screens extracted into screen docs; a seeded flow-versus-screen conflict. Drafts go in `.superpowers/work/`. Results go in `docs/status.md`.

## Out of scope

- a validator script (checks stay prose, as with flows)
- visual styling in wireframes
- persona simulation over screens
- design-system or token specs
These go in `docs/status.md` as future work.

## Open questions

| # | Question | Assumption made meanwhile |
|---|---|---|
| 1 | Should `used_by` be kept at all, or derived by the evaluator? | Keep it as informational; flows win on conflict. |
| 2 | Element id format (`E1` vs semantic ids)? | `E1`... for stability under edits. |
