# Finding gaps

Input: screen, component, and flow docs, and raw wireframes, in any mix. Find what is absent, interview the user on each candidate, then offer to design missing pages. Raw wireframes are read as is; this mode never converts them (`convert-existing-doc.md` does). The three evaluation lenses of `evaluate-flows.md` are not run.

## Missing pages

1. **Collect targets.** Links, buttons, tabs, menu items, screen Exits, and flow transitions whose target screen or state has no supplied doc. External URLs and `mailto:` are never candidates. A submit or primary action that leaves the page, where the docs state or imply leaving but name no destination (sign-in "then signs the user in"), is collected too, labelled by the action (`Sign In (submit)`); an action that stays on the page is never a candidate.
2. **Classify by context.** A *navigation* is a header, footer, nav, or tab bar item, or inline text such as "Forgot password?". A *title* is a heading naming the page's own subject: `Sign Up` centered at the top of `sign-up.md` is a title, but `Sign Up` as a link in a header is a navigation. Only navigations and leaving submit or primary actions are candidates; one that cannot be classified stays a candidate.
3. **Resolve** each candidate against the supplied docs by id, route, or title. A match by any of the three drops the candidate. A submit action with no named destination has nothing to match and goes to the interview.
4. **Interview** the rest (survey rules below). Question: `Target: <label> on <doc>`. Options: **Not a navigation**, **Goes to an existing page** (the user names it), **Missing page**, **Skip**. Not a navigation: no edit, the candidate is dropped. Goes to an existing page, name given: cite that doc's id where the citing doc points (small correction): a flow transition (`via <exit>`) cites the screen id, a raw wireframe link is rewritten to it, and a citing screen's or component's Exits stay as they are (they name no destination); name not given: ask once, otherwise record nothing. Missing page: proceeds to the design offer in step 5. Skip becomes an Open question on the citing doc (`Origin: added`, `Resolve in: product`).
5. **Offer design.** Ask "Design the missing pages now?" once, after the interview. Yes: write a draft `kind: screen` doc per missing page from `screen-template.md`, with an Open question for everything the citing docs do not imply (no invention), and cite the new screen ids: a flow transition (`via <exit>`) cites the new id, a raw wireframe link is rewritten to it, the new screen's own `used_by` lists the citing flows, and a citing screen's or component's Exits stay as they are (they name no destination). No: record each as an Open question on the citing doc (`Origin: added`, `Resolve in: product`).

## Missing behaviors

1. **Name entities and states.** Each thing users create or change (email, image, order) and the states the docs imply (draft, sent, published). Name an entity or state only when a doc names it.
2. **Build the matrix.** Rows are the verbs the docs define; columns are the entity's states plus the counterpart role (who receives the sent email, who views the published image). Each cell is defined, absent, or n/a. The matrix is working notes, not an output doc.
3. **Pick candidates.** Absent cells, only in three cases: a state-changing verb exists and the docs never say what other states allow (edit after publish); a one-sided pair (send without receive, create without delete, publish without unpublish); a state entered with no exit. An entity with one state yields no candidates.
4. **Interview** (survey rules below). Question starts `Entity: <name> on <doc>` and is specific to the state: "Can the user edit a published image?" Options: the plausible readings, then **Skip**. When the answer names the behavior, apply it as a small correction to the doc that owns the entity. Skip becomes an Open question on that doc (`Origin: added`, `Resolve in: product`).
5. **Exclude technical gaps** (network, double-tap, permissions plumbing), as `evaluate-flows.md` does.

## Order of a run

1. **Missing pages first**, then behaviors (new pages can add entities and states).
2. **One summary** of candidate counts for both parts, before the interview.
3. **Interview** each part the user accepts. Ask nothing about a part the user declined.

## Survey rules

Use the survey rules in `evaluate-flows.md`, with these exceptions: one question call per part (pages, behaviors) instead of per step-4 group; the question prefix is `Target: <label> on <doc>` for pages and `Entity: <name> on <doc>` for behaviors; the Skip option is labelled `Skip`. Everything else (at most 4 questions per call, at most 3 readings plus Skip, Skip last, no recommendation that presumes intent) is as in `evaluate-flows.md`.
