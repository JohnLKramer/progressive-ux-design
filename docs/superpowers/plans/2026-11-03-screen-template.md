# Screen Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `screen-template` mode to the `progressive-ux-design` skill: one standalone doc per screen, linked from flows by id, with evaluation and conversion support.

**Architecture:** One new template file (`screen-template.md`) in the same style as the flow templates, routed from `SKILL.md`. Existing files get small additions: a `screen:` field in the low-level flow template, a wireframe case in conversion, and screen lenses in evaluation. This is a prose skill, so each task is verified the way `docs/status.md` records earlier work: baseline agents without the change, then agents with it, plus grep checks for structure.

**Tech Stack:** Markdown skill files, Claude subagents as test runners. No code.

**Spec:** `docs/superpowers/specs/2026-11-02-screen-template-design.md`

## Global Constraints

All skill files live in `skills/progressive-ux-design/` (the repo root symlink `progressive-ux-design-skills` points at `skills`; never edit through it twice).

- Flow only: no visual aesthetics. Wireframes show structure.
- One layer per document. Link by id, never copy content.
- A parameter (number, duration, threshold, member of a fixed set) goes in the External parameters table, `Value` = the source's value else `unspecified`, `Rubric` = path/URL else `none yet`. Prose refers to it by name.
- A gap becomes an Open question with `Origin` (`source` | `added`) and `Resolve in` (`high` | `low` | `persona` | `product`). Don't invent.
- Rewrite relative links so they resolve from the output file's own directory.
- Final screen docs go in `ux/screens/<id>.md` unless the user says otherwise. Drafts and test runs only in `.superpowers/work/`.
- Screen owns local behavior (stays, opens a modal, saves). Flow owns the journey (where an exit leads).
- Spec decision this plan changes: screen element ids are `El1`, `El2`... not `E1`..., because the low-level flow template already uses `E1`.. for exits and a flow transition would be ambiguous ("E4 tap"). Record this in the status doc (Task 5).
- Stage files you change (`git add`); commit through the commit proposal tool when the user approves.

## Review Focus

1. A screen with no loading or error behavior (a static screen): expected "n/a, because ..." rows, not silently missing rows or invented states.
2. A screen doc is not a flow: `evaluate-flows.md` currently says a doc without `level:` front matter triggers "convert to high or low?". A screen doc has `kind: screen` and no `level`; it must not trigger that.
3. A screen used by no flow yet (`used_by: []`): not a finding.
4. `wireframe:` points at a path that does not exist: finding, not a crash or silent pass.
5. A thin source (a wireframe and nothing else): conversion yields a complete template with a states table limited to what the wireframe shows, and open questions for the rest.

---

## Milestone 1: Screen template and routing

### Task 1: Baseline without the skill change

**Files:**
- Create: `.superpowers/work/screen-baseline/game-picks.md` (agent output, not committed)
- Create: `.superpowers/work/screen-baseline/the-stash-screen.md` (agent output, not committed)

**Interfaces:**
- Produces: two baseline outputs and a short notes file `.superpowers/work/screen-baseline/notes.md` listing what each invented or omitted (layout, states, ids, exits). Task 2 closes the gaps found here.

- [ ] **Step 1: Run two agents with the current skill, no screen mode.** Agent A prompt: "Using the progressive-ux-design skill, turn `.superpowers/example/screens/game-picks.md` into a standalone doc describing that one screen. Write it to `.superpowers/work/screen-baseline/game-picks.md`." Agent B: same, for "the Stash screen" from `.superpowers/example/flow-docs/the-stash.md`, output `the-stash-screen.md`.
- [ ] **Step 2: Record observations in `notes.md`.** For each output: which sections it used, whether it has a states table, element ids, exits, open questions, and whether the two outputs share a layout. Expected: different layouts, no state matrix, flow-shaped output.
- [ ] **Step 3: Stage nothing** (work files stay untracked).

### Task 2: `screen-template.md` and router entry

**Files:**
- Create: `skills/progressive-ux-design/screen-template.md`
- Modify: `skills/progressive-ux-design/SKILL.md` (mode table, "Free text" line, "Locations", description front matter)

**Interfaces:**
- Produces: the screen doc shape. Front matter keys `id`, `kind: screen`, `title`, `status`, `purpose`, `route`, `personas`, `used_by`, optional `wireframe`. Section headings in this fixed order: `## Purpose and success criteria`, `## Rules`, `## Wireframe`, `## Elements`, `## States`, `## Actions`, `## Exits`, `## External parameters`, `## Out of scope`, `## Open questions`, `## Conversion note`. Element ids `El1`..; actions `A1`..; screen state ids `SS1`.. (not `S1`, which flows use). Exits are named kebab-case, no destinations.
- Table columns: Elements `Id | Element | Shows | In states`; States `State | Entry condition | Elements that change | Wireframe`; Actions `# | Element | Trigger | Guard | Local result | Exit`; Exits `Exit | Reached from | Meaning`.

- [ ] **Step 1: Write the failing structural check.** Create `.superpowers/work/screen-baseline/check-template.sh` that exits non-zero unless `skills/progressive-ux-design/screen-template.md` exists and contains every heading above, and `SKILL.md` contains the string `screen-template`. Run it: `bash .superpowers/work/screen-baseline/check-template.sh`. Expected: FAIL (file missing).
- [ ] **Step 2: Write `screen-template.md`** in the format of `low-level-flow-template.md`: a fenced markdown template, then `## Fill rules`. Fill rules must state: (a) loading, empty, error each get a state row or an explicit `n/a, because <reason>` row; (b) `wireframe:` is either an inline fenced block under `## Wireframe` or a relative path in front matter, and callouts in the wireframe are written `[El3]` and resolve to the Elements table; (c) `used_by` is informational, may be empty, and flows win on conflict; (d) screen-local results only: the Actions table never names a destination screen or flow state, only an `Exit`; (e) the spec's ownership rule in one sentence; (f) unknown states, copy, or guards become open questions, not invention; (g) wireframes carry structure only.
- [ ] **Step 3: Edit `SKILL.md`.** Add a row `screen-template | One screen: elements, states, actions, exits; may embed or link a markdown UI wireframe. Used by many flows. | screen-template.md`. In "Free text" add: input describing one screen's elements and states routes to screen. In "Locations" add `screens` to `kind`. Add "screens" to the front-matter description trigger list. Keep SKILL.md under its current ~45 lines plus the added lines.
- [ ] **Step 4: Run the check.** `bash .superpowers/work/screen-baseline/check-template.sh`. Expected: PASS.
- [ ] **Step 5: GREEN run.** Repeat Task 1's two agent prompts with the changed skill, outputs to `.superpowers/work/screen-green/`. Expected: both outputs share the template layout; each states table has the three required-state rows (or `n/a`); element ids `El#`; wireframe callouts resolve; the Actions table names no destinations; thin-source gaps are open questions with `Origin: added`. Record gaps in `.superpowers/work/screen-green/notes.md` and close each by editing `screen-template.md`.
- [ ] **Step 6: Stage.** `git add skills/progressive-ux-design/screen-template.md skills/progressive-ux-design/SKILL.md`

---

## Milestone 2: Integration with flows

### Task 3: Flow link and conversion case

**Files:**
- Modify: `skills/progressive-ux-design/low-level-flow-template.md` (States table, fill rules)
- Modify: `skills/progressive-ux-design/convert-existing-doc.md` (step 1 classify, step 2 choose target, mapping table)

**Interfaces:**
- Consumes: Task 2's screen doc shape and ids.
- Produces: flow States table gains a `Screen` column (a screen id or `none`), placed after `State`. A flow transition may name a screen action as `<screen-id>.A<n>` in `User action`. Conversion handles a "wireframe or single-screen description" input class.

- [ ] **Step 1: Write the failing check.** Extend `check-template.sh` into `check-integration.sh`: fails unless `low-level-flow-template.md` contains `| State | Screen |` and `convert-existing-doc.md` contains `wireframe`. Run: expected FAIL.
- [ ] **Step 2: Edit `low-level-flow-template.md`.** Add the `Screen` column to the States table. Existing `Screen / surface` column stays for journey-specific surface text; rename nothing else. Fill rule: when a state is a screen with its own doc, set `Screen` to its id; the flow's "Shows" holds only journey-specific variation; transitions cite screen actions as `<screen-id>.A<n>`.
- [ ] **Step 3: Edit `convert-existing-doc.md`.** Classify gains "single-screen doc or markdown UI wireframe". Target: `screen-template`. Mapping rows: wireframe → embedded block or `wireframe:` path (keep the file if it is a standalone markdown UI, link by relative path); elements visible in the wireframe → Elements with `El#`; states beyond what the wireframe shows → open questions (`Origin: added`), never invented; actions the source implies → Actions rows with local result unknown if not stated. A flow's screen content found while converting a flow: leave in the flow, add a `Screen` pointer only if the screen doc exists.
- [ ] **Step 4: Run the check.** Expected: PASS.
- [ ] **Step 5: Regression run.** One agent converts `.superpowers/example/flow-docs/the-stash.md` to low-level with the changed skill. Expected: output still follows the low-level template, with `Screen` set to `none` where no screen doc exists (no invented screen ids). Output to `.superpowers/work/screen-green/stash-low.md`.
- [ ] **Step 6: Stage.** `git add skills/progressive-ux-design/low-level-flow-template.md skills/progressive-ux-design/convert-existing-doc.md`

### Task 4: Evaluation of screens and screen-flow conflicts

**Files:**
- Modify: `skills/progressive-ux-design/evaluate-flows.md`
- Create: `.superpowers/work/screen-eval/` fixtures (a screen doc from Task 2's GREEN output, a low-level flow referencing it, and a seeded-conflict copy; not committed)

**Interfaces:**
- Consumes: Task 2 screen shape; Task 3 `Screen` column and `<screen-id>.A<n>` convention.
- Produces: evaluate accepts docs with `kind: screen` (no `level`), and a new lens table row set. Findings feed the existing summary and survey procedure unchanged.

- [ ] **Step 1: Build fixtures.** In `.superpowers/work/screen-eval/` put `game-picks-screen.md` (Task 2 output), `flow-clean.md` (a low-level flow whose state S2 has `Screen: game-picks-screen` and a transition citing `game-picks-screen.A2`), and `flow-conflict.md` (same, but the transition's reaction says the screen moves to S3 while the screen's A2 `Local result` says "stays on screen", and a second transition cites `game-picks-screen.A9`, which does not exist).
- [ ] **Step 2: Baseline run** with the current `evaluate-flows.md` on `game-picks-screen.md` + `flow-conflict.md`. Expected: the agent asks whether to convert the screen doc (no `level`), or misses the conflict. Record it.
- [ ] **Step 3: Edit `evaluate-flows.md`.** (a) Intro: a doc with `kind: screen` is evaluated as a screen; it never triggers the "convert to high or low" question. (b) Add a lens table for screens: Ambiguity (an element or state that reads two ways), Consistency (callouts vs Elements, `In states` vs States rows, Actions vs Exits), Completeness (the required states or `n/a`, every action with trigger and local result, every Exit declared). (c) Add cross-doc checks, counted as cross-doc conflicts in the summary: every flow `Screen` id resolves; every cited action exists; every Exit a flow uses exists; screen `used_by` matches flows that reference it (empty `used_by` is not a finding); a screen's `Local result` vs a flow transition's reaction. (d) A `wireframe:` path that does not resolve is a consistency finding. (e) Survey rule: for a screen-vs-flow conflict the options are "change the screen", "change the flow", Skip; mark the side the ownership rule recommends as "(owner by the rule)" without recommending intent; a skipped one becomes an Open question with `Resolve in: low`.
- [ ] **Step 4: GREEN run** on `game-picks-screen.md` + `flow-conflict.md`, and a second on `flow-clean.md`. Expected: conflict run reports the A2 contradiction and the missing A9 as cross-doc conflicts, no convert question, survey options as in (e); clean run reports zero cross-doc conflicts and does not flag empty `used_by`. Close gaps in `evaluate-flows.md`.
- [ ] **Step 5: Stage.** `git add skills/progressive-ux-design/evaluate-flows.md`

---

## Milestone 3: Record

### Task 5: Status doc and example

**Files:**
- Modify: `docs/status.md` (add "Session 4: screen template (2026-11-03)")
- Modify: `skills/progressive-ux-design/SKILL.md` (only if the "Not covered yet" line needs a screen-validator pointer)
- Create: `.superpowers/example/screens/game-picks.screen.md` (the Task 2 GREEN output, cleaned, as the worked example)

**Interfaces:**
- Consumes: all prior tasks' notes.

- [ ] **Step 1: Write the status section** in the same style as Sessions 2 and 3: what was added, baseline vs GREEN results (counts, not adjectives), what was not tested, known limits. Include: the `El#` decision and why; persona simulation, a validator script, and design-token specs not done; one product domain only; single runs.
- [ ] **Step 2: Copy the example** from `.superpowers/work/screen-green/game-picks.md`, fix any open gaps noted in `notes.md`, and add `used_by: []`.
- [ ] **Step 3: Verify.** `grep -c "screen-template" skills/progressive-ux-design/SKILL.md` prints 1 or more; `grep -n "Session 4" docs/status.md` finds the section.
- [ ] **Step 4: Stage.** `git add docs/status.md .superpowers/example/screens/game-picks.screen.md skills/progressive-ux-design/SKILL.md`

---

## Self-review notes

- Spec coverage: template and ordered sections (Task 2); ownership rule (Task 2 rule d, Task 4 e); wireframe embed or path (Task 2 b, Task 4 d); flow link and router (Tasks 2, 3); conversion (Task 3); single-screen and cross-doc evaluation (Task 4); testing and status (Tasks 1, 5); out-of-scope items recorded (Task 5). The spec's two open questions are settled: `used_by` kept, informational (Task 2 c); element id format `El#` (Global Constraints).
- Types: `El#`, `A#`, `SS#`, `<screen-id>.A<n>`, `Screen` column are named once in Task 2/3 Interfaces and used identically in Task 4.
