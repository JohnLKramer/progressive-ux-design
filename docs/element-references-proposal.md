# Referencing HTML files and elements from flow and screen docs

## What you asked for

Let flow and screen docs point at an HTML file, and at specific elements inside it.

## Assessment

The earlier draft of this file spent its effort on classes. Your ask is about HTML files and specific elements, so most of that is not needed. What it got right still holds:

1. **Ids are not unique across docs.** `El1` exists on every screen. A flow cannot cite an element without saying which screen.
2. **HTML has its own `id` and `class` attributes.** They exist for styling and scripts. If we reuse them for `El#`, a designer's CSS cleanup silently breaks the docs. The templates also say "structure only", and HTML classes are a styling tool.
3. **Ids never renumber.** Anything we put in the HTML must follow the same rule, or links rot.
4. **The docs already have one place that owns elements: the screen.** A flow reaches elements through its `Screen` id. Giving flows a second way in, straight to the HTML, creates two owners.

What it got wrong for this ask: classes. Nobody has said they need "all three buttons". Drop them until someone does.

## Proposal

### 1. Link the HTML file from the screen (and component)

Reuse the existing `wireframe:` front-matter field. A path ending in `.html` is an HTML wireframe. No new field.

```yaml
wireframe: ../mockups/game-picks.html
```

Components get the same field. Today they must be inline only; allow a path for HTML.

### 2. Bind elements with a `data-el` attribute

Each element in the HTML carries `data-el="El3"`, the same id as its Elements row.

```html
<button data-el="El3">Lock picks</button>
```

- `data-*` attributes are their own namespace, so HTML `id` and `class` stay free for styling. Do not use `id="El3"`; one binding only.
- It replaces the `[El3]` callout used in markdown sketches. The same "every callout resolves, every element has one" rule applies, with the same `not drawn` exception.
- Ids are screen-local, as today. Inside a component's own HTML, ids are component-local.

Two more attributes, because all three baseline runs invented them:

- `data-action="A2"` on the node that triggers an action (the Actions table's `Element` row). A node with several actions is not allowed; give sub-parts their own element.
- `data-exit="write-reason"` on the same node when that action has an Exit.

`<main>` carries `data-screen="<screen-id>"` and `data-state="SS1"`, so the file says which state it draws.

Every element row has exactly one `data-el` in the HTML. There is no `Locator` column, because the skill writes the HTML and can always add the attribute.

### 3. A screen that uses a component marks only the slot

In the screen's HTML, the component is one element: `data-el="El2"`. Its inner pieces are not marked. This matches the markdown rule ("no sketch of its own"). The component's own HTML marks its own elements.

### 4. Flows cite elements as `<screen-id>.El3`

Same shape as `<screen-id>.A<n>` and `<component-id>.A<n>`, so nothing new to learn. Allowed where a flow already names screen content:

- `Shows` in the States table (`game-picks.El3`)
- prose and Open questions

Flows do not link HTML files directly. The path is stated once, on the screen. A flow state with no screen doc yet stays `Screen: none`; the next layer creates the screen.

### 5. Per-state HTML

The States `Wireframe` column already takes a name or `same`. Allow a path to a different HTML file there. One file per state. Showing and hiding states inside one file is out of scope.

### 6. Checks (added to `evaluate-flows.md`)

Read HTML by searching for `data-el=`, never by reading the whole file.

| Check | Fails when |
|---|---|
| Path resolves | `wireframe:` points at a missing file |
| Every `data-el` has a row | The HTML marks an element the table lacks |
| Actions and exits match | `data-action` and `data-exit` values differ from the Actions and Exits tables |
| Every row is found | A row has no `data-el` in the HTML and is not `not drawn` |
| No duplicates | Two elements share a `data-el` in one file |
| Flow citations resolve | `<screen-id>.El#` names a screen or element that does not exist (only when that screen doc was supplied) |

`find-gaps.md` and `convert-existing-doc.md` need one line each: an HTML wireframe is read through `data-el`, and a source HTML file is linked, not copied.

### 7. The HTML is built from the screen doc

The screen doc is the source of truth; the HTML is derived from it (and from the markdown wireframe, "mockdown", when there is one). Built HTML:

- has one `data-el` per Elements row, and nothing marked that the table lacks;
- follows the wireframe's regions and order;
- is more realistic than mockdown: real controls, real layout, copy from copy keys or the source;
- is a design artifact, not product code;
- has no script and no behavior: no id-overlay toggle, no handlers. Inspection tools can show `data-el`.

Rebuilding is allowed when the doc changes. Hand edits to the HTML are kept only if they keep the `data-el` checks passing. When doc and HTML disagree, the doc wins.

This needs a new mode, `build-html`: input is a screen or component doc; output is the `.html` file at `ux/mockups/<id>.html` (or where the user says) and the `wireframe:` path set. It is a small file, like `find-gaps.md`.

## Files that change

| File | Change |
|---|---|
| `screen-template.md` | `wireframe:` accepts `.html`; fill rule for `data-el`; slot rule for components |
| `component-template.md` | `wireframe:` accepts `.html`; same `data-el` rule |
| `low-level-flow-template.md` | Fill rule: `<screen-id>.El<n>` in `Shows` and prose |
| `evaluate-flows.md` | The checks above |
| `build-html.md` (new) | The build mode above |
| `find-gaps.md`, `convert-existing-doc.md` | One line each |
| `SKILL.md` | Router row for `build-html`; one line in the rules for every output; the "structure only" rule gets an exception for built HTML |
| `docs/status.md` | Session entry |

One new mode, one new file.

## Not covered

- Classes or group references. Add later only if someone needs "all of these elements".
- A script to run the checks. They stay prose, like the others.
- Styling. The HTML may have it; the docs ignore it.
- Several states in one HTML file.

## Settled

- Flows reach HTML only through the screen.
- The skill builds the HTML, so `data-el` is always available.
- One HTML file per state, for now.

## Decision

Built HTML is unstyled semantic HTML: real controls in layout order, browser-default look. This keeps the "structure only" rule for the docs; the build mode gets a scoped exception.

Later goal, not in scope here: use these base pages to build a design system and produce styled pages. See `scratch/next-goal-design-system.md`.

## Next steps

Per `writing-skills`, each edit above needs a failing baseline first: an agent with the current skill converts an HTML mockup and we record what it does. Then the edits, then a re-run. I have not started that.
