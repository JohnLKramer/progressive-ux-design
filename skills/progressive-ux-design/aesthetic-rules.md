# Aesthetic rules

The rulebook for `critique-aesthetics.md`. Every finding cites one row by id. Sources: **RUI** = Refactoring UI, "7 Practical Tips for Cheating at Design"; **LUI** = Learn UI Design, "7 Rules for Creating Gorgeous UI" (parts 1 and 2), "Color in UI Design: A Practical Framework" and "3 Pro Tips on Alignment"; **PT** = Butterick's Practical Typography, "Summary of Key Rules".

Measure from the CSS where you can (computed size, `line-height` over `font-size`, `max-width` in characters, shadow values, distinct hues). A size the CSS leaves to the browser default is measured at the browser's default value. When you estimate from a screenshot, say so in the finding.

A fix never names a colour value that is not already on the page. Where a fix needs a new colour (a secondary grey, a hover shade, an outline colour, an accent for A1), write the direction instead ("a lighter tint of the body text colour", "a darker, more saturated shade of the button fill") and add `needs colour approval`. If the user has named an approved palette, the fix names the palette entry and still carries `needs colour approval`.

For C4, compare colours in HSB. A colour written in HSL converts as V = L + S x min(L, 1 - L) and S(hsb) = 2 x (1 - L / V), with S and L as fractions.

| Id | Rule | Broken when | Src |
|---|---|---|---|
| T1 | Body text is 15–25px. | Body text under 15px or over 25px. | PT |
| T2 | Line spacing is 120–145% of the font size. | Body paragraph `line-height` under 1.2 or over 1.45. | PT |
| T3 | Lines run 45–90 characters. Measure with `scripts/measure_line_length.py` (see `critique-aesthetics.md`) and use each block's `t3` value. | A multi-line block whose full lines run over 90 characters (`too-long`) or whose typical full line is under 45 (`too-short`). A one-line block is exempt. | PT |
| T4 | Two weights do the work: one normal (400 or 500) and one heavy (600 or 700). Count every weight on text in the page: title, headings, nav, buttons, body. Weights within a tier are one tier; 800 and above is a third. | More than two weight tiers in use (for example 400, 600 and 800), or a weight under 400 at a small size. | RUI |
| T5 | Hierarchy comes from colour and weight, not size alone: a dark colour for primary text, a grey for secondary (dates, notes), a lighter grey for ancillary. Count text colours on the page background; white text on a dark fill is not counted. | Secondary text (dates, notes, captions) has the same colour as primary text, levels differ only by font size, or more than three text colours are in play. | RUI |
| T6 | Emphasis is rationed. Bold and italic never together; all caps only under one line, with 5–12% extra letter-spacing; centred text sparingly; underline only on links and on actions deliberately styled as links (see B1). | Any of those broken, or strikethrough or a text highlight used as an ordinary style. | PT, LUI |
| T7 | Only the page title gets every emphasis at once. Every other element mixes emphasis up with emphasis down. | A non-title element that is large, bold, capitalised and high contrast all at once; or a hover or selected state that changes size or weight and shifts the layout. | LUI |
| T8 | Type is clean and neutral. | A script, decorative or monospace face for general UI text, or the unstyled browser-default Times or Arial. | PT, LUI |
| C1 | Layout works in grey; colour adds one or two hues with purpose. | Three or more accent hues, or groups that are only told apart by colour. | LUI |
| C2 | De-emphasise on colour by reducing contrast in the background's own hue, never with grey. | Grey text on a fill of any hue (a neutral white or grey fill does not count). Fix: white text at lower opacity, or a colour of the background's hue. | RUI |
| C3 | Text over an image has a method behind it: dark image, overlay, text box, blur, floor fade or scrim. | Light text on a bright or busy image with none of those. | LUI |
| C4 | Variations of one colour (hover, pressed, selected, tints) are derived from it in HSB: a darker variant has lower brightness and higher saturation, a lighter one higher brightness and lower saturation, and the hue barely moves. | A darker state with equal or lower saturation than its base (it looks greyed or dull), a lighter state more saturated than its base, or a state that switches to a different hue family. | LUI |
| S1 | Whitespace is generous, and space between groups exceeds space within them. | The gap between sibling groups (cards, sections) is under 1.5x the largest gap inside one of them, ignoring the group's own padding (the 1.5x is this rulebook's test, not the guide's), or lines and labels are crammed against their neighbours. | LUI |
| S2 | Separate with shadow, background tint or spacing before reaching for a border. | Borders are the only separator between adjacent elements, or the page feels ruled and boxed in. | RUI |
| L1 | Text beside a hard-edged element (an image, a card, a rule) faces it with the text's flush edge, because a ragged edge aligns only weakly. | The text's ragged edge faces the hard edge: left-aligned text with an element on its right, or right-aligned text with an element on its left, so the gap between them varies line to line. Fix: put the element on the text's flush side, stack the two, or centre both on one axis. | LUI |
| L2 | Icons, bullets and quote marks hang outside the text edge so the letters share one line. | Icons, bullets or quote marks sit on the text column, so the text's left edge looks indented against headings and other text. Fix: pull them into the margin (negative offset) or give the list a gutter, so the labels start where the headings start. | LUI |
| D1 | Light comes from above: shadows are offset down, raised things are lighter on top, inset things (fields, pressed buttons) look sunk. | Shadows with large blur or spread and no vertical offset, shadows falling upward, or inset and raised treatments swapped. | RUI, LUI |
| I1 | Icons drawn for 16–24px stay near that size. | An icon scaled to about 3x or more of its drawn size. Fix: keep it small inside a tinted shape. | RUI |
| A1 | A bland page gets a small accent: a coloured border on an alert, the active nav item or the top of the layout. | Every surface neutral with no accent anywhere. | RUI |
| B1 | Buttons follow hierarchy, not semantics: one solid primary, outline or low-contrast secondaries, link-style tertiaries. This row judges only how the buttons rank against each other visually, never which action ought to be primary. | Two or more solid fills competing in one group; red or green used as a fill on an action that is not the page's primary action; or a destructive action (cancel, delete, remove) carrying the solid fill outside a confirmation dialog. | RUI |

## Severity

- **High**: page-wide, or it changes the page's first impression (body type, text hierarchy, the primary-action treatment, a wall of competing fills).
- **Medium**: repeats across a component, such as every card.
- A1 is always Low: it names something missing, not something wrong.
- **Low**: one instance, or polish. Any measure within 10% of its limit, taken as a share of the limit, is Low, whatever its scope.
