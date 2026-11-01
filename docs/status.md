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

## Session 3: persona simulation (2026-10-31)

Added `simulate-flows.md` (persona agent loop, engagement rubric, quit rule, interview, runs recommendation) and `simulate-report.md` (report, recommendations, improvement survey), routed from the skill. Research basis: `.superpowers/work/research/engagement-research.md`. Rubric anchors, quit thresholds and the run-count rule are design choices, not validated; the strongest cited evidence is two preprints read at abstract level.

- Baseline (2 agents, no skill): both wrote a one-pass analyst-voice review. No simulation, no engagement scores, no quit point, no interview, no deviation tracking.
- GREEN (1 run, acquisition-low + gambling-novice, me as orchestrator): persona stayed in voice, scored every step, left at step 6, explained the signup refusal in its own words. Gaps closed: round E down, narrate missing flow content neutrally, return visits are not simulated.
- Not done: the report and improvement-survey steps were not run end to end; only interview question 1 of 8; no high-level flow run; one run, no pressure scenarios; the 80% agreeableness check is untested. Nested orchestration (a subagent running the whole skill) is untested because subagents may not spawn agents.

### Session 3, full run on the-stash (high), fantasy-grinder, 3 runs

Report, recommendations and improvement survey ran end to end; all 5 recommendations adopted and applied to the flow work copy (`.superpowers/work/green/stash-high.md`, now with open questions 13 and 14).

- Result: 0/3 completed the profile goal. Runs 1 and 2 ended at step 2 (quit rule fired on two low-relevance steps); run 3 went 7 steps. Quit steps differ by 5, so the rule says add 2 runs; not done.
- Fixes to the skill from this run: interview replies are prose only (a persona leaked the PRIVATE/SAY/DO block); resend rule for missing replies; first step can ride in the start prompt.
- Reliability problem: replies from resumed persona agents often arrived a turn late or only after a resend request. Runs depend on resuming one agent per persona; a more robust design would resend the persona's step history in each message. Not changed.
- Still not done: interview questions 2-8 (only question 1 asked in every run); one persona; low-level flow with several personas; the 80% agreeableness check only passed trivially.
- Outcomes depend partly on the incidental detail I gave (run 2's 20-minute lock clock); treat the quit counts as soft.

### Session 3, reliability change: stateless foreground calls

Replaced "one resumed agent per run + SendMessage" with one fresh foreground Agent call per step (and per interview question), each carrying the persona brief plus the run log.

- Test: stash flow again (updated doc), same 3 situations. 9 calls in 3 rounds (steps 1 and 2 for 3 runs, then step 3 for 2 runs plus an interview question for the run that had ended): all returned in the same cycle, no resends, no format failures, interview came back as prose. Before, most replies needed a resend or arrived a turn late.
- Replies can still come as hand-back messages, not the tool result; match by agent id (skill updated).
- Cost: about 52k tokens per call as reported by the harness, so a run is roughly 52k x steps. Interviews cost one call per question: 8 per run if all asked, which is the dominant cost.
- Runs were not driven to completion in this test (run 2 ended at step 2; runs 1 and 3 stopped at step 3). Only the mechanism was tested, not a full report.
- In this rerun with the adopted changes: run 2 still left at step 2 (no inactives news); runs 1 and 3 stayed longer, liked seeing when the pick locks, and balked at "saving publishes your reason under your name" (not covered by the open questions beyond OQ6).
