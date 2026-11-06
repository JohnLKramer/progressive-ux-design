# Find gaps mode: missing pages and missing behaviors

Date: 2026-11-06. Status: draft for review.

## Intent

Add a mode to the `progressive-ux-design` skill that reads a set of UX docs and finds what is absent: **missing pages** (a link or action points at something with no doc) and **missing behaviors** (a state-dependent capability the docs leave undefined). It interviews the user about each candidate and, for missing pages, offers to design them.

Said by the user: find missing pages from undefined link or action targets, guessing from mockup context (Sign Up is a link in a header, a title at the top center of `sign-in.md`); interview the user on each (not a navigation / goes to an existing page / missing); then ask whether to design the missing pages. Missing behaviors depend on application state (send an email but receive undefined; publish an image but edit undefined).

Decided in brainstorming: new mode with its own file; lifecycle-matrix method; inputs are screen, component, flow, and raw wireframe docs; three interview answers plus Skip; a "yes" to design produces draft screen docs.

## Placement

- New file `skills/progressive-ux-design/find-gaps.md`, one router row in `SKILL.md` (mode `find-gaps`), a line in the Not covered / status docs.
- Reuses `evaluate-flows.md` survey rules by reference (interactive tool, at most 4 questions per call, at most 3 readings plus Skip, Skip last, skipped becomes an Open question). Does not run the three evaluation lenses.
- Raw wireframes (not in template format) are read as is; this mode never converts them (`convert-existing-doc.md` does).

## Part 1: missing pages

1. **Collect targets**: links, buttons, tabs, menu items, screen Exits, and flow transitions whose target screen or state has no supplied doc.
2. **Classify by context.** A *navigation* is a header, footer, nav, tab bar item, or inline text such as "Forgot password?". A *title* is a heading naming the page's own subject (centered "Sign Up" at the top of `sign-up.md`). Unclear ones stay candidates.
3. **Resolve** each navigation against supplied docs by id, route, or title. A match is dropped.
4. **Interview** (survey rules). Question: `Target: <label> on <doc>`. Options: **Not a navigation**, **Goes to an existing page** (user names it), **Missing page**, **Skip**. Skip becomes an Open question on the citing doc (`Resolve in: product`). "Not a navigation" and "existing page" are recorded as small corrections only when the user names the target. Where the id goes: a flow transition (`via <exit>`) cites the screen id; a raw wireframe link is rewritten to it; a citing screen's or component's Exits stay as they are (they name no destination).
5. **Offer design**: "Design the missing pages now?" Yes: write a draft `kind: screen` doc per missing page from `screen-template.md`, with open questions for everything the citing docs do not imply, and cite the new screen ids: a flow transition (`via <exit>`) cites the new id, a raw wireframe link is rewritten to it, the new screen's own `used_by` lists the citing flows, and a citing screen's or component's Exits stay as they are (they name no destination). No invention beyond what the citing docs imply. No: record each as an Open question on the citing doc (`Origin: added`, `Resolve in: product`).

## Part 2: missing behaviors

1. **Entities and states**: each thing users create or change (email, image, order) and the states the docs imply (draft, sent, published). Name an entity or state only when a doc names it.
2. **Verb by state matrix** (kept in the working notes, not the final doc): rows are verbs the docs define; columns are the entity's states plus the counterpart role (who receives the sent email, who views the published image). Each cell is defined, absent, or n/a.
3. **Candidates** are absent cells only when: a state-changing verb exists and the docs never say what other states allow (edit after publish); a one-sided pair (send without receive, create without delete, publish without unpublish); or a state is entered with no exit.
4. **Interview** (survey rules). Question starts `Entity: <name> on <doc>`; state-specific, e.g. "Can the user edit a published image?" Options are the plausible readings, then Skip. Answers apply as small corrections; Skip becomes an Open question (`Resolve in: product`, `Origin: added`).
5. Technical gaps (network, double-tap, permissions plumbing) are out of scope, as in `evaluate-flows.md`.

## Order of a run

Pages first, then behaviors (new pages can add entities and states). One summary of candidate counts before the interview; the interview asks nothing about a declined part.

## Testing

Per the repo pattern: baseline agents without the mode, GREEN agents with it, a REFACTOR round for gaps they report.

Fixtures: (a) a header doc with a Sign Up link beside a `sign-in.md` with a centered Sign Up title; (b) a publish-only art app; (c) a send-only email app; (d) a clean set with no gaps, which must yield zero candidates.

Check: Sign Up in the header is a candidate and the title is not; the interview shape and Skip handling match; the matrix finds edit-after-publish and receive; no technical gaps are raised; the clean set yields none. Record results and not-done items in `docs/status.md`. Single runs, no formal pressure scenarios (technique skill).

## Out of scope

Persona simulation of new pages, validator scripts, converting raw wireframes, design tokens.
