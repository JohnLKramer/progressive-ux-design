# High-level flow template

Experience-level journey. Not a state machine; name only the transitions that matter to how the user feels. Copy the skeleton, fill every slot. Empty slot → write `none` or move the gap to Open questions.

```markdown
---
id: <kebab-case>
level: high
title: <what the user is trying to do>
status: draft            # draft | reviewed
personas: [<persona-id>] # or [unspecified]; cite ids only
entry_points: [<where the user starts>]
goal: <one sentence, user's goal and the product's goal>
success_criteria: [<observable outcomes>]
preconditions: [<what must be true on entry>]
refined_by: []           # ids of low-level docs that detail this flow
source: <original doc path or "free text">
---

# <title>

## Journey
<!-- 3-10 beats, in order. Ids B1, B2... are stable; low-level docs cite them. -->

### B1: <beat name>
- **User does / wants:** 
- **User sees / experiences:** 
- **Sentiment risk:** <what could delight or frustrate here, and for whom>
- **Next:** <B2 | "declines -> B4" | "-> other-flow-id" | end>

## Rules and incentives
<!-- Business rules in words only; values live in the parameters table. -->

## External parameters
| Name | Kind (numeric/enum) | Used in | Value | Rubric |
|---|---|---|---|---|
| bonus_amount | numeric | B3 | unspecified | `none yet` |

## Open questions
| # | Question | Why unresolved at this level | Origin | Resolve in |
|---|---|---|---|---|

## Conversion note
<!-- Converting only: dropped / assumed / missing. -->
```

## Fill rules

- Beats describe experience, not UI. Layout, copy, and per-control reactions belong to low level.
- Sentiment risk is REQUIRED on every beat, stated as a sentence. If it can't be judged, say what is unknown; a question goes in Open questions only if someone else must decide it.
- Source front matter maps: `primary_persona`→`personas`, `entry_point`→`entry_points`, `primary_goal`→`goal`, `preconditions`→`preconditions`.
- A rule that needs a value reads like: "Units expire after the expiry window (see parameters)."
- A beat with nothing special to see: write `nothing distinct`. A beat that ends the flow: `Next: end`.
- Branches: only those that change the experience (decline, error the user feels, return visit). Skip the rest.
- Rubric path for a value not defined anywhere: `none yet`. Keep it in the table so it can be written later.
