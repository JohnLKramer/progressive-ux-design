# Planted usability defects (facts about this fixture)

Workspace: `planted_usability/`, page `profile`, style `plain`. It plants one defect for each WCAG row added to `skills/design-refine/critic.md` after the first release. The existing rows (contrast, focus, labels, keyboard) are deliberately clean.

- 1.4.10 Reflow. Where: `styles/plain/style.css`, `[data-sp="shell"]`. Fact: `width: 1100px` with no media query.
- 1.4.12 Text Spacing. Where: `[data-sp="card"]`. Fact: `height: 96px; overflow: hidden; line-height: 24px !important`.
- 2.4.2 Page Titled. Where: `pages/profile/index.html`. Fact: `<title>Page</title>`.
- 2.5.5 Target Size. Where: `[data-sp="dismiss"]`. Fact: an 11px `x` link, one per card.
- 4.1.3 Status Messages. Where: `El2`. Fact: the "Saved!" toast has no `role` or `aria-live`.

Also present, and covered by Nielsen rather than a WCAG row: the vague heading "Stuff", the label "Thing 1", the "Invalid input" message with no suggestion, and the links "Read more" and "Click here".

The Save button is about 42px tall and must not be reported under 2.5.5: it is not a defect the fixture plants.
