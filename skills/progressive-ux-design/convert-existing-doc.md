# Converting an existing document

Best effort. The input may lack the detail the target needs; deliver a complete template with gaps listed.

1. **Classify** the input: flow doc, user/persona doc, or segmentation doc. Several inputs → one output per flow or persona.
2. **Choose the target** unless the user named one:
   - Flow with per-screen actions and reactions → low-level, and also high-level if asked for both.
   - Flow that is a narrative, outline, or only goals and steps → high-level.
   - Low-level asked of a thin source → produce it with `(assumed)` rows and Open questions.
   - High-level asked of a detailed source → collapse screens into beats; push UI detail out, keep a `refined_by` pointer to the low-level doc.
3. **Load** the matching template file and fill it.
4. **Map** source content:

| Source content | Goes to |
|---|---|
| Numbers, thresholds, lists of allowed values, amounts | External parameters (keep the source's rubric link; else `none yet`) |
| Questions, TBDs, "proposed", "pending review" | Open questions, source wording kept |
| Business rules | Rules section (both levels); condition on one transition → guard (low) |
| Edge-case table | Transitions (low); named branches or sentiment risk (high) |
| Layout, copy, hit areas (when target is high) | Dropped from the output; mentioned once in the conversion note |
| Evidence, limitations, confidence (persona) | Tags and Gaps; keep confidence |

5. **Don't invent.** Unknown stays a gap. Inferred content is tagged. Contradictions in the source are listed, not resolved.
6. **Conversion note**: fill the template's `## Conversion note` section: what was dropped, assumed, and missing for this level. Open questions the source already asked keep `Origin: source` and their wording.
7. Preserve ids and cross-links from the source, rewriting relative paths for the new location. Rename front-matter fields to the template's names (see the template's fill rules).
