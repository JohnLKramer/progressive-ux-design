# Report, recommendations, improvement survey

Input: the run files from `simulate-flows.md`. You write the analysis; personas never do.

## 1. Report

Save to `.superpowers/work/sim/<flow-id>/report.md` (final location: the user's choice), then show the user the summary. Shape, in order:

1. **Header:** flow id and level, personas, runs each, persona confidence, one line that results are hypotheses from simulation, not user research.
2. **Per persona:** completion `k/n`; where runs ended (step id and why, in the persona's words); mean E at each step; one line each for friction, surprise, delight, engagement, from the transcripts and interview.
3. **Deviations:** every place a run left the intended path (the path to the flow's success criteria; you derive it, the persona never sees it). Columns: persona, runs affected, step, what it did instead, why (persona's words), classification (`confusion`, `friction`, `boredom`, `irrelevant`, `deliberate choice`, `flow gap`).
4. **Across personas:** which steps lose whom. Flows aimed at one persona still report all of them.
5. **Reliability check:** completion above 80% across personas, or no run quit on a Relevance <= 2 step: say the simulation may be too agreeable. Say where runs diverged.

## 2. Recommendations

Emphasis follows level: high-level flows lean to engagement (dull, irrelevant, wrong order); low-level to usability (missed control, unclear copy, too many steps). Report both when seen.

One row each:

| # | Step id | Kind (`usability`/`engagement`) | Scope (`specific`/`general`) | Problem and evidence (runs, personas) | Recommendation |
|---|---|---|---|---|---|

A general problem ("screen too cluttered", "topic is boring") may have a vague recommendation ("add visual interest") or `none specific`. Don't invent precision. Order by personas and runs affected.

Then ask: "Walk through these recommendations and update the flow?"

## 3. Improvement survey (only on yes)

Interactive question tool, one question per recommendation, at most 4 per call, in table order. Each starts `Flow: <id>, Step: <id>`, states the problem in one sentence, then offers exactly:
- **Adopt this recommendation**
- **No, leave it**
- **Improve it some other way** (ask a follow-up for their idea)

Apply: adopt → edit the doc (same ids and paths; keep it in its template, `convert-existing-doc.md` shape rules). A recommendation that needs a decision the doc can't carry (copy, a value) becomes an Open question (`Origin: added`). Other way → apply their idea. No → leave unchanged and add nothing.

Offer a re-run of the changed steps afterwards; don't start it unasked.
