# Planted defects (facts about this fixture)

Workspace: `pages/booking` with styles `plain` (carries the planted style defects) and `bold` (no planted defects).

- Layer: style-only. Where: `styles/plain/style.css`. Fact: "Cancel reservation" is a solid dark fill, the loudest control in each card, while "Add to calendar" is a faint outline. A good fix quiets Cancel (outline or text weight) and gives the non-destructive actions the visual weight, editing only `style.css`/`layout.css`.
- Layer: style-only. Where: `styles/plain/style.css` (`body`). Fact: body text `#9a9a9a` on `#ffffff` is about 2.8:1, below 4.5:1. A good fix darkens the text colour (and the muted link and button text) to at least 4.5:1.
- Layer: structural. Where: `pages/booking/index.html`, `El2` credits section. Fact: the balance is one undifferentiated paragraph with no number/label split. A good fix splits it into a prominent number and a label (existing roles such as `price`/`text`), keeping every `data-el`, `data-action` and `data-exit` marker and all words.
- Layer: structural. Where: `pages/booking/index.html`, each `El4` card. Fact: "Cancel reservation" comes before "Add to calendar" and "Bring a friend" in DOM order, and all three buttons are siblings in one ungrouped row. A good fix reorders the DOM so the main actions come first and the destructive action is separated or grouped (for example a `part` with variant `actions`), without losing markers.
- Layer: unfixable without a doc row. Where: `pages/booking/index.html`, `El4` cards. Fact: no element shows the studio name, and the doc defines no `data-el` for one, so a critic will likely flag "no studio shown". A fix needs a new element row in the doc, so no fixer can resolve it; the correct outcome is to report it, not invent an element.
