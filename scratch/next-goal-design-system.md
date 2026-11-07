# Next goal: from base pages to a design system and styled pages

Not now. The HTML work comes first, and this is where it is headed.

## Where we start

Built HTML is unstyled semantic HTML: real controls in layout order, browser-default look, one `data-el` per element row. See `docs/element-references-proposal.md`.

## Where we want to get

1. Use those base pages as the starting point for a design system (tokens, component styles).
2. Apply it to the same pages to get styled versions.

## What to keep in mind now

- Keep the base HTML free of styling decisions, so a stylesheet can be added later without editing the markup.
- Keep `data-el` stable. A style layer and any later checks can rely on it.
- Components are already their own docs, so they are the natural first units of the design system.
- Styled pages are a new layer. The "structure only" rule in the templates would then need a scoped exception, as with built HTML.

## Open when we get there

- Where tokens live and who owns them.
- Whether styled pages are rebuilt from the docs or are a separate artifact.
- How to check a styled page still matches its doc.
