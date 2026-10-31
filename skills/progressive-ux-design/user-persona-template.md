# User persona template

Written so a later evaluator can judge flows against it. Every claim carries provenance.

Tags: `[S]` stated by the source · `[H]` stated by the source but labeled a hypothesis or untested there · `[I]` inferred (say from what) · `[M]` missing (the slot stays, with the question).

```markdown
---
id: <kebab-case>
name: <one-line description of the person>
status: draft            # draft | grounded
confidence: low          # low | medium | high
source: <doc path (repo-relative), research, or "free text">
---

# <name>

## Demographics
age_range / occupation / location_type: value with tag

## Personality
## Goals
## Knowledge            <!-- what they know, including known_products they expect patterns from -->
## Non-knowledge        <!-- what they do not know; includes this product -->
## Domain knowledge     <!-- none | casual | enthusiast | expert, plus tag -->
## Technical fluency    <!-- low | medium | high | expert, plus tag -->
## Patience             <!-- low | medium | high; give_up_after: what makes them quit -->
## Engagement           <!-- what draws and keeps them -->
## Frustrations         <!-- what drives them away -->
## Voice                <!-- how they talk; one invented example labeled as such -->

## External parameters
<!-- Only values the product team decides, e.g. a give-up threshold. Observed figures (counts, survey %) are evidence: keep them inline with their evidence id. -->
| Name | Kind | Used in | Value | Rubric |
|---|---|---|---|---|

## Gaps and tensions
<!-- [M] items, plus places where the source contradicts itself. Keep the contradiction; don't smooth it. -->

## Conversion note
<!-- Converting only: dropped / assumed / missing. -->
```

## Fill rules

- Every section present, even if only `[M]`.
- Scale values (low/medium/high, none/casual/enthusiast/expert) are defined here, not parameters.
- Source evidence: keep evidence ids, inline figures, and the confidence level; drop verbatim quotes.
- Source field mapping: `domain_knowledge`, `tech_fluency`, `patience`, `give_up_after`, `demographics` → same-named sections; `known_products` → Knowledge; `limitations` → Gaps and tensions; "Who they are" → Personality; "What they do NOT know" → Non-knowledge. A source value the source says it could not observe → `[M]`.
- One bullet = one claim = one tag. Bulleted, short, concrete behaviors over adjectives.
- Enumerated fields use the listed values; anything else goes in prose beside it.
- Market segmentation input: one persona per segment; shared traits are repeated, not cross-referenced.
- Demographics from population statistics are not traits of the persona: leave the value `[M]` and add a separate `[I]` bullet saying so.
