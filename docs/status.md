# Status: readiness for the future skills

Written at the end of the first session (2026-10-31). Covers what exists, how it was verified, and how ready it is for each planned skill.

## What exists

| Piece | Where |
|---|---|
| Router skill `progressive-ux-design` | `skills/progressive-ux-design/SKILL.md` |
| High-level flow template | `skills/progressive-ux-design/high-level-flow-template.md` |
| Low-level flow template | `skills/progressive-ux-design/low-level-flow-template.md` |
| User persona template | `skills/progressive-ux-design/user-persona-template.md` |
| Conversion procedure (existing doc → template) | `skills/progressive-ux-design/convert-existing-doc.md` |
| Flow evaluation (ambiguity, consistency, completeness, survey) | `skills/progressive-ux-design/evaluate-flows.md` |
| Plugin manifest | `.claude-plugin/plugin.json` |

The spec's goal list has a "Detailed flow template" bullet between high and low. It has no mode of its own in the spec, so it is treated as the low-level template.

## How it was verified

- Baseline: three agents with no skill converted example docs. Content was good, but each invented a different layout.
- GREEN: four agents with the skill (stash → high, acquisition → low, fantasy-grinder → persona, free text → high). All produced the template shape and routed correctly.
- REFACTOR: gaps they reported were closed (conversion-note slot, persona parameters, placeholder rules, front-matter mapping, link rewriting, open-question origin). Two re-tests followed.
- Not done: no formal pressure scenarios. This is a template and technique skill, so application and missing-information tests were used instead.
- Samples are single runs, not 5+ reps per variant.

## Readiness for the future skills

| Future skill | Ready? | What helps | What is missing |
|---|---|---|---|
| Evaluate consistency of high-level flow | Mostly | Fixed section order, stable ids (B1..), `Next` field, parameter table, `refined_by` | Machine-checkable rules (every `Next` resolves; every parameter used is in the table; every `Used in` beat exists). Needs a written checklist. |
| Evaluate persona against high-level flow | Mostly | Per-beat Sentiment risk to score; persona fields for patience, give-up, frustrations, engagement, voice; provenance tags that let a judge weight claims | A scoring output format (per beat: reaction, confidence). Persona `[M]` gaps will make some judgments low-confidence; the evaluator must say so. |
| Update high-level flow from subjective output | Partly | Open questions table with `Resolve in`; stable beat ids to cite | A rule for when the evaluator may edit a beat and when it must raise an open question. Version or change log field is absent. |
| Evaluate consistency and completeness of low-level flow | Mostly | State, transition, exit tables; completeness check list in the template; `parent` and `From beat` links | The checks are prose, not a script. A validator could check dangling states, unreachable states, and missing action rows. `(assumed)` rows need a policy. |
| Evaluate persona against low-level flow | Partly | Same persona fields; transitions with system reactions | Low-level states carry no sentiment field, so the evaluator would walk paths and infer feelings. Consider a path-walk procedure. |
| Update low-level flow from subjective output | Partly | Same as the high-level update | Same gaps, plus keeping low-level consistent with its `parent` high-level doc after edits. |

## Known limits

- Example data came from one product domain (sports picks). Templates were not tried on other domains except one free-text yoga-booking input.
- Persona to flow linking is by id only; there is no registry that lists personas and flows.
- The skill does not yet tell users about the missing evaluation skills beyond a pointer to this file.
- Parameter "kind" is only numeric or enum.

## Suggested next steps

1. Write the checklist for high-level consistency; it is the smallest gap and unlocks the other five skills.
2. Add a persona-versus-beat output format.
3. Decide whether low-level states need an optional sentiment field.

## Session 2: flow evaluation (2026-10-31)

Added `evaluate-flows.md`, routed from the skill. It covers the spec's consistency and completeness goal.

- Baseline (3 agents, no guidance): all edited docs on assumptions (e.g. changed a 30-day return to S1), added their own open questions, dumped every concern in one long reply, no skip option, no ordering, no per-flow labels, and raised completeness before asking.
- GREEN (1 agent, stash-high + acquisition-low together): matched the spec's order, labels, skip option, and gating. Gaps it reported were closed: batch limits, summary counting, template-format findings out of scope, when docs get rewritten.
- Not done: re-test after the gap fixes, and a low-level-only or single-doc run. One sample, no pressure scenarios.
- Evaluation now exists, so the "Evaluate consistency" rows above are partly met; the machine-checkable checklist is still missing.
