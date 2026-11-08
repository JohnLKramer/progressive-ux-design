# Role vocabulary

Every styled element in a saved page or mockup carries one of these roles.

## Roles

- `header` — top bar of the page or of a section
- `nav` — group of navigation links
- `hero` — large introductory banner
- `section` — titled block of related content
- `card` — self-contained boxed item
- `card-list` — collection of cards
- `media` — image, video, or illustration
- `heading` — title text
- `text` — body copy
- `button` — clickable action
- `link` — inline navigation target
- `input` — single form field
- `form` — group of inputs and actions
- `tabs` — set of switchable views
- `list` — plain list of items
- `table` — tabular data
- `badge` — small status or count label
- `avatar` — user or entity picture
- `price` — monetary amount
- `footer` — bottom bar of the page or of a section
- `part` — named region inside a card, header or other repeated item (variant says which: `time`, `main`, `venue`, `action`, `summary`, `media`, `body`, `actions`, `profile`)

## Wrappers

- `shell` — outermost page frame
- `content` — main content column
- `sidebar` — secondary column beside the content

## Markup

A role is written as the attribute `data-sp="<role>"` on an existing element. Wrappers are written the same way: `data-sp="shell"`, `data-sp="content"` and `data-sp="sidebar"`. A variant is written as `data-sp-variant="<free text>"`.

A page may also mark an element with the standard `hidden` attribute, for a copy the source showed only at another screen size and for decoration with no words (map tiles). Hidden text still counts as content, and at least 90% of the visible words must stay visible. An element the source hid stays hidden, and a subtree with no words may not hold a form control or a `data-el`, `data-action` or `data-exit` element.

## Layout rules

`layout.css` may not use any of the following:

- `display: none`
- `visibility: hidden`
- `order`
- `flex-direction` values that end in `-reverse`
- `flex-flow` values that contain `reverse`
- `grid-area`
- `grid-row`
- `grid-row-start`
- `grid-row-end`
- `grid-column`
- `grid-column-start`
- `grid-column-end`
- `grid-template`
- `grid-template-areas`
