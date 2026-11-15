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
| Component template (shared screen pieces, cited by id) | `skills/progressive-ux-design/component-template.md` |
| Find gaps (missing pages and behaviors; interview, then design offer) | `skills/progressive-ux-design/find-gaps.md` |
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

## Session 4: screen template (2026-11-03)

Added a screen mode: `screen-template.md` (one screen, own id, used by many flows; elements, state matrix, actions, exits, parameters; embeds or links a markdown UI wireframe). Also: a router row in `SKILL.md`, a `Screen` column in the States table of the low-level flow template, a wireframe conversion case in `convert-existing-doc.md`, and screen and screen-flow evaluation in `evaluate-flows.md`. Design spec and plan are under `docs/superpowers/`. A worked example is at `.superpowers/example/screens/game-picks.screen.md` (git-ignored, like all of `.superpowers/`; `used_by: []`).

Decision: ids are `El#` (elements), `A#` (actions), `SS#` (screen states), not `S#`. The low-level flow template already uses `E#` and `S#`, so a shared prefix would make an id ambiguous across a flow and the screen it uses. Ids are integers only and never renumbered. Exits are named handoffs with no destinations; the flow resolves them.

### Results by task

- Task 1, baseline (2 sonnet agents, no screen hint; game-picks wireframe and the-stash): both fell back to the low-level flow template. 0 of 2 had element ids, a layout section, or a state matrix. game-picks added 2 assumed states and 9 assumed of 10 transitions, the-stash added 1 state variant and 4 assumed of 19 transitions; game-picks dropped the wireframe, the-stash its mermaid diagram. 10 and 14 open questions.
- Task 2, GREEN (2 agents, same inputs): both used the template layout with `El#`/`A#`/`SS#` ids, kebab-case exits, no destinations in Actions, and gaps recorded as open questions. gaps closed: callouts only in a legend, `El8a`-style ids, n/a state rows without ids and unlabelled overlay states, wireframe invented from a layout table, `screen` Element and implied-but-unshown actions. After review, the 2 agents were re-run and spot-checked with grep only, not read in full. game-picks ended with 16 elements, 2 actions, 1 exit, 10 open questions.
- Task 3, integration: check script RED 2 failures (no Screen column, no wireframe case), then PASS. Regression: 1 agent converted the-stash to low-level, all template sections present, Screen column set to `none` on 7 of 7 states, 0 invented screen ids, 0 `El#`/`SS#`/`A#` leaks.
- Task 4, evaluation (fixture pairs: flow plus screen, clean and with 2 seeded contradictions, A2 stays vs moves and a missing A9). Baseline: found both, but as "conflicts between two flows", with no ownership marker and intent-presuming options. GREEN: 2 cross-doc conflicts found, options Change the screen / Change the flow / Skip, owner by rule, skipped items become Open questions on the flow (`Resolve in: low`). Clean pair: 0 cross-doc conflicts, empty `used_by` not flagged, no convert question. Rule the GREEN run forced: a contradiction between two docs is not a gap, and an Open question on one side does not suppress it (the run suppressed the A2 conflict because the screen's Q3 covered El6).

### Review rounds

- Milestone 1 (Tasks 1 to 2): 5 Important fixed in 1 round. They were: literal n/a example row, source-silent state wording plus Open question, `not drawn` exception for elements in undrawn states, non-conversion wireframe sketch note, and the router tie-breaker (connected screens: low-level; one screen in isolation: screen).
- Milestone 2 (Tasks 3 to 4): 5 Important and 3 spec gaps fixed in 1 round. Survey groups 2 to 4 now cover screens with `Flow: <id> vs Screen: <id>` prefixes; the summary shows `<id> (screen)`; the owner rule covers which Exits exist (screen) and where an Exit leads (flow); a `used_by` mismatch is a step-2 correction (flows win); the covered-gap rule is stated once. The spec gaps were lens rows for parameters-in-table and every element in a state, and a convert row for states the source shows. Re-test: clean pair 0 conflicts; conflict pair run 1 suppressed A2 (the rule above), run 2 found both.

### Not done

- Persona simulation over screens (`simulate-flows.md` is unchanged).
- A validator script; the checks are still prose.
- Design-token specs; the template is structure only.
- A re-run of the Task 4 clean evaluation after its last rule sentence; not re-run after the contradiction sentence; the clean pair has no contradictions, so no change is expected.
- `<screen-id>.A<n>` was not exercised end to end by the Task 3 regression run; its flows had `Screen` set to `none` throughout.
- Runs on any domain other than sports picks.
- Single runs, no repetitions.
- A linked `wireframe:` path, including the key-under-`## Wireframe` rule.
- A `wireframe:` path that does not resolve (Review Focus 4 has a rule, no test).
- Routing free text to screen mode (every run named a file and said "one screen").
- A static screen with real `n/a, because <reason>` rows (game-picks only had "source does not show it").
- An author writing a flow with a real `Screen` id (only hand-made fixtures).
- Visual styling in wireframes (spec out-of-scope).
- The spec's testing plan said "the Stash flow's screens" (plural); only one Stash screen was extracted.

### Spec deviations

Beyond the ids (`El#`/`A#`/`SS#`): transitions cite `<screen-id>.A<n>` (not the spec's `E4 tap`), and the flow gets a `Screen` column in States (not a `screen:` field). The spec carries a superseded note.

### Final review fixes

The final whole-branch review findings were fixed in a later commit (`fix: address final review findings`): evaluate row loads `screen-template.md`; Exit naming in flows (`via <exit-name>`); safe `used_by` rule with partial input; unsupplied screen ids not checked; embed-by-default for wireframes; `source:` on screens; precedence rule for `In states`, `used_by` YAML example, router and description wording, and `none` Exit exception. The Milestone 1 minors were closed and re-reviewed clean, so no deferred minors remain.

## Session 5: component template (2026-11-03)

Added `component-template.md` so a shared piece (header, tab bar) is written once and cited by screens, as flows already cite screens. Screens gain `components:` front matter, a `component: <id>` Elements row, and `<component-id>.A<n>` action citations. Router, convert (offer, never extract unasked), and evaluate (component lens, screen-vs-component cross-doc checks, owner rule) are updated. Design: `docs/superpowers/specs/2026-11-03-component-template-design.md`.

Not done: no agent runs of the new evaluate checks or conversion offer (prose reviewed only); nested components, parameterized variants, and validators are out of scope.

## Session 6: find gaps (2026-11-06)

Added `find-gaps.md`, routed from the skill (router row, free-text rule, description). It reads a set of UX docs and finds what is absent: missing pages (a link or action points at something with no doc) and missing behaviors (a state-dependent capability the docs leave undefined, including the counterpart role, such as the receiving side of a sent item). It does not convert docs first. Each candidate goes to the user as an interview question (last option Skip); skips become Open questions citing the doc, with `Origin: added` and `Resolve in: product`. After the interview, missing pages get one design offer. Design: `docs/superpowers/specs/2026-11-06-find-gaps-design.md`; plan: `docs/superpowers/plans/2026-11-06-find-gaps.md`. The `SKILL.md` "Not covered yet" line is unchanged (it is about validators, which this mode does not add). `README.md` does not list modes or files, so it is unchanged.

### Results

- Baseline (3 sonnet agents, no mode; pages, art-app, email-app fixtures, single runs): all converted first without being asked. None split page gaps from behavior gaps or classified links against titles. None named a missing page as a target (pages run reported "nothing links to Sign In"; no Pricing or Forgot password?). art-app found the post-publish gap (unpublish, edit, delete) only as one item among 12 mixed with out-of-scope items (upload failure, limits, empty gallery, sign-in). email-app never named the receiving side. None offered design. Technical gaps (upload failure, limits) were raised.
- GREEN (same fixtures plus a clean one, single runs): pages found Pricing and Forgot password? and dropped Home, Sign Up, Get started as resolved; titles were not candidates. art-app found edit draft, edit published, unpublish, delete, and who sees a draft, with 0 page candidates and no technical gaps. email-app found the receive gap, plus edit sent, delete or unsend sent, remove attachment, leave without sending, and one page candidate (where the user lands after Send). clean raised 0 candidates and invented nothing.
- Gap closed in a fix round: the first pages run dropped Sign In and Create account submit buttons as having no target. The mode now collects a submit or primary action that leaves the page when the docs state or imply leaving but name no destination.
- Ruling: implementers could not dispatch test agents, so the controller ran all baseline and GREEN runs.

### Review rounds

- Milestone 1 (Tasks 1 to 2): spec compliant; 1 Important fixed in 1 round (what "Not a navigation" and "Goes to an existing page" answers do). Review clean after the round.
- Milestone 2 (Tasks 3 to 4): no milestone review; the final whole-branch review is the gate.

### Not done

- Single runs only; no repetitions on any fixture.
- No formal pressure scenarios.
- Interviews were simulated: the test agents had no interactive question tool, so every answer was Skip. A non-Skip path (for example "Goes to an existing page" as a correction) was not run.
- The design offer was specified but never exercised: the "yes" path (draft `kind: screen` docs, `used_by` and Exits updates in citing docs) was not run. The agents asked the offer once after the interview and the answer was not simulated.
- The submit-action rule (added in the fix round): exercised once (email-app Send); not exercised on the pages fixture.
- Review focus items not exercised: an external URL or `mailto:` target (no fixture has one), a one-state entity, and a drafted missing page with no invention (the "yes" path).
- Domains other than the fixtures (pages, art-app, email-app, clean).
- Evaluation lenses were not run in the email-app run (the vague "short" confirmation duration was left alone).
- No validators; the checks are prose.

### Spec deviations

- Additions beyond the spec: the submit-action collection rule, the external-URL exclusion, the one-state exclusion, "Not a navigation" drops the candidate with no edit, the `used_by`/Exits rewrite (where the id goes per kind of citing doc), and the `Entity:` question prefix.
- Skip label: `Skip` here versus `Skip (decide later)` in `evaluate-flows.md`.

### Deferred minors

- `find-gaps.md:7`: dense; baseline `notes.md` is not per-run five-column.
- `find-gaps.md:10`: "ask once, otherwise record nothing" does not say whether the candidate is dropped.
- Steps 1 to 3 do not say how to handle screen Exits and flow transitions when only screen docs are supplied.
- Skip the design offer when there are no Missing page answers; say whether it follows the pages interview or both.
- Whether "not yet created" counts as a state for the one-state rule.
- What to write for a "not allowed" answer, and which doc owns an entity shown in several docs.
- How the user accepts or declines each part.

## Session 7: HTML wireframes (2026-11-06)

Screens and components can link an HTML mockup, bound to the doc by `data-el`. Added `build-html.md` (builds unstyled semantic HTML from a screen or component doc); `wireframe:` accepts `.html`; `data-action` and `data-exit` mark actions and exits; flows cite `<screen-id>.El<n>`; evaluate, convert, find-gaps and the router are updated. Design: `docs/element-references-proposal.md`. Later goal: `scratch/next-goal-design-system.md`.

- Baseline (3 sonnet agents, game-picks, no guidance): three different front-matter keys (`html:`, `html:`, `mockup:`), one used `id` alone, all invented `data-action`/`data-exit`, all added a doc section or note, one added an id-overlay script, all guessed styling.
- GREEN (same 3 prompts): all used `wireframe:`, 16 of 16 `data-el`, no `id="El#"`, no style or script, doc diff 1 to 3 lines. Checked by grep, not in a browser.
- Not done: single runs; one fixture (screen only, SS1 only); components, non-default states, and flow `<screen-id>.El<n>` citations not exercised; evaluate checks not run; no pressure scenarios.
- Seen in GREEN, unsettled: which node holds `data-el` for a group (run3 put it on `nav`); `source:` path rewrite; whether a pointer sentence under `## Wireframe` is allowed (run2 added one); heading levels and whether chips are buttons.
- Second GREEN (2 runs, after adding four rules to `build-html.md`: `data-el` on the wrapping node for a multi-part element, tags follow role, doc edits limited to `wireframe:` plus Open questions, `source:` untouched): both runs had 16 of 16 `data-el`, no `id="El#"`, no style or script, chips as text, `data-el` on `nav`, and a doc diff of exactly one line. Still unsettled: placeholder label format for avatars, doctype/`lang`/`title` boilerplate, element order inside a card, and the doc naming no element locations (the `El#` ids are the only reference).
- Component and evaluate runs (1 each): the component build followed `build-html.md` (root `data-component`, no `data-state`, 2 of 2 `data-el`, action and exit on the same node, doc diff one line). Evaluate on a screen with 4 seeded HTML defects (an `id="El3"`, a missing `data-el`, an extra `data-el`, an action not in the table) and a flow citing a missing element: all found, with the right counts. It also corrected the flow's dangling `game-picks.El99` to `El9`, which was a guess. Rule added to `evaluate-flows.md` (dangling element or action citation is a question, never a correction); that rule was not re-run. Not tested: a flow citation that resolves, a component slot in a screen's HTML, a non-default state file.

## Session: design-refine (2026-11-09)

Added the `design-refine` skill (`skills/design-refine/`): an orchestrator `SKILL.md`, a critic brief, two fixer briefs, and three scripts (`ledger.py`, `gates.py`, `render.py`). Spec: `docs/superpowers/specs/2026-11-09-design-refine-design.md`. Plan: `docs/superpowers/plans/2026-11-09-design-refine.md`. `python3 -m pytest tests/design_refine` passes; the full suite (`python3 -m pytest tests`) was not run.

### Bake-off that chose the critic

Four critique skills (humbleteam, Prasad, grapeot, design-loop's critic) were each run twice, in fresh subagents, on `classpass-profile` in `big-box-gym`. All agreed on the real problems; they differed in output shape, layer-tag cleanliness and actionability. The critic brief is a rewrite built on humbleteam's structure (MIT) with Prasad's vocabulary (MIT); no grapeot text is included (no licence). One page and one style only.

### Live runs on the planted workspace

Workspace: `tests/design_refine/fixtures/planted/`, style `plain`, cross style `bold`, `--max-iterations 4`, critic and fixers on `sonnet`.

- **Baseline (no skill), 2 agents.** Both edited CSS freely (one also edited the page HTML and moved elements), used no ledger or gates, and did not render. Both runs were contaminated: one read the fixture's answer-key file in the workspace root, the other a comment in the CSS. Both have since been removed from the fixture, so the baseline needs re-running to count as evidence.
- **GREEN, happy path, 1 run.** Four iterations, four fixes kept (F1 contrast, F2 loudest Cancel, F3 faint Add to calendar, F6 identical button names), loop stopped on `cap`. The critic accounted for every open id each review, did not re-raise fixed findings (the ledger marked them fixed), and the ambiguous finding (credit balance) went to needs-you and stayed there. The one structural fix (F6) passed the marker gate and the cross-style compare. The ledger view kept fixers' approaches away from the critic.
- **Defects found by the live run, fixed:** the report omitted findings still open at the cap (F4 was open and unmentioned); the fixture leaked its own answer key.
- **Findings not fixed:** a screenshot-only compare returns `same` for a markup- or accessibility-only fix (aria-labels), so for those the only checks are the marker diff and validators. During the run the critic was told to write `critique.json` itself to save controller context; `SKILL.md` says the orchestrator saves the reply.

### Not run live (covered only by scripted tests or not at all)

- A fix that fails the gate and is restored, with a real fixer.
- A finding ending `unresolved` after two attempts.
- The doc-backed structural path (edit the doc, `build-html`, `make-stylable`).
- The run on the bake-off page (plan Task 12 step 4).
- Several styles in one run; `--bar` other than P2.
- Cost: about 25 subagent dispatches for 4 kept fixes.

## Session: style-switcher content emphasis (2026-11-09)

Styled pages spent each brand's colors on the title and header only; key figures, statuses and cards looked the same in every style. Plan: `nimbalyst-local/plans/let-s-improve-the-stylized-melodic-puffin.md`.

- Vocabulary: new role `stat` (key figure; variant `primary` for the lead figure), status variants for `badge` (`positive`, `negative`, `pending`, `live`, `neutral`), and `part` variants `head`, `meta`, `row`. The finalize lint now requires a `[data-sp="stat"]` rule in every style.
- `make-stylable.md` step 4: "Mark what a reader scans for", with the Stash card as a worked example.
- `extract-style.md`: tokens `accent-2`, `positive`, `negative`, `pending`; new step 6 item "Emphasis" (three tiers, accent inside content, tabular stats, tinted status pills, card head band, status edge, meta chips, screenshot self-check).
- `visual_check.py`: new `flat-content` problem when no visible heading, stat, price or badge inside `content` differs from the body text color or background. Runs in both display modes.
- `python3 -m pytest tests/style_switcher`: 681 passed.
- End to end in a temp workspace: make-stylable on `pc-ux-design/screens/html/stash.html` (validates; 19 `stat`, 3 status badges, 3 `head`, 3 `meta`, 10 `row`), styles extracted from `scratch/examples/dk` and `scratch/examples/prizepicks` (both finalize `ok`), acceptance passes on all 4 combinations. With the dk emphasis rules commented out, acceptance fails with `flat-content` in both modes. The styles were written in this session, not by a fresh agent following the skill, so whether an agent follows the new emphasis guidance is not yet tested.
- `flat-content` looks only inside `content`; a stat panel in a `sidebar` is not checked. `role_check.py` reports totals, not a count per role.
