---
name: progressive-ux-design
description: Use when writing, refining, restructuring, reviewing, or checking user-experience flows for ambiguity, consistency, or completeness, or user personas, when given an existing UX flow doc, user description, or market segmentation doc to put into a standard format, or when a flow needs more or less detail than its current layer.
---

# Progressive UX Design

UX is designed in layers. Each layer fixes only what that layer can decide; everything else becomes an **open question** for a later layer. Flow only: no visual aesthetics.

## Route by mode

Load ONLY the file for the chosen mode. Templates are the output shape; fill every slot.

| Mode | Use for | Load |
|---|---|---|
| `high-level-flow-template` | Experience-level journey; judge user impact and sentiment. Not a state machine. | `high-level-flow-template.md` |
| `low-level-flow-template` | Mostly-complete state machine of screens, user actions, system reactions. | `low-level-flow-template.md` |
| `user-persona-template` | Who the user is, for judging flows. | `user-persona-template.md` |
| `evaluate-flows` | Check one flow or a group for ambiguity, consistency, completeness; small fixes, then a survey. | `evaluate-flows.md` (granularity follows each doc's `level`; also load that level's template when correcting) |

**Existing document not in template format** (flow, user description, segmentation): also load `convert-existing-doc.md`. It picks the mode unless the user named one.

**Free text, no mode named:** choose by detail in the input. Journey or intent → high-level. Per-screen actions and reactions → low-level. Description of people → persona. State the choice in one line in your reply (not in the document).

## Rules for every output

- One layer per document. Link layers with ids (`parent`, `beat`/`state` refs), never by copying content.
- A **parameter** is a number, duration, time, threshold, or member of a fixed set that the product team decides. It goes in the **External parameters** table: `Value` = the source's value, else `unspecified`; `Rubric` = path/URL, else `none yet`. Prose refers to it by name ("the expiry window"), never inlines it. A value the source refers to but doesn't give ("some cutoff", "the morning of") is implied; anything else is not, so don't add it.
- A gap becomes an **Open question**, tagged with `Origin` (`source` if the input asked it, `added` if you found it) and `Resolve in` (`high`, `low`, `persona`, `product`). Don't fill gaps with invention.
- Converting? End the doc with a `## Conversion note` (dropped, assumed, missing). Not converting: omit it.
- Rewrite relative links so they resolve from the output file's own directory.
- Referenced personas or sibling flows that aren't supplied: cite the id only; don't create them.
- Best effort: a thin input still yields a complete template, with gaps listed.

## Locations

Final docs: where the user says, else `ux/<kind>/<id>.md` (`kind` = `flows` or `personas`). Intermediate drafts only: `.superpowers/work/`.

## Not covered yet

Scoring personas against flows, or auto-improving templates: see `docs/status.md`. Tell the user these don't exist yet.
