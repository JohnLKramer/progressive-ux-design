"""Mechanical visual checks for a styled page: what the rendered layout must not look like.

`MEASURE_JS` runs in the switcher shell page and measures the preview iframe; `evaluate_visual`
judges the numbers. Problems come back as `code: message` strings.

- card-not-one-row: a card with three or more visible parts whose parts do not share a row (layout applied only).
- duplicate-nodes: two visible nav, tabs or list elements, neither inside the other, with the same text.
- bullets: a visible list item in a role container that still shows a list marker.
- sidebar-too-wide: a visible sidebar at least 40% of the viewport (layout applied only).
- horizontal-overflow: the page is wider than the viewport.
"""
from __future__ import annotations

from typing import Any, Dict, List

MAX_SIDEBAR_SHARE = 0.4
OVERFLOW_TOLERANCE_PX = 1

MEASURE_JS = """() => {
  const frame = document.getElementById('frame');
  const w = frame.contentWindow, d = frame.contentDocument;
  const shown = (e) => e.getClientRects().length > 0 && w.getComputedStyle(e).visibility !== 'hidden';
  const norm = (s) => s.replace(/\\s+/g, ' ').trim();
  const box = (e) => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right}; };
  const cards = [];
  d.querySelectorAll('[data-sp="card"]').forEach((card) => {
    if (!shown(card)) return;
    const parts = Array.from(card.children).filter((c) => c.getAttribute('data-sp') === 'part' && shown(c)).map(box);
    if (parts.length >= 3) cards.push({parts: parts});
  });
  const groups = {};
  d.querySelectorAll('[data-sp="nav"], [data-sp="tabs"], [data-sp="list"]').forEach((e) => {
    if (!shown(e)) return;
    const text = norm(e.innerText || '');
    if (text.length < 6) return;
    (groups[text] = groups[text] || []).push(e);
  });
  const duplicates = [];
  Object.keys(groups).forEach((text) => {
    const els = groups[text];
    if (els.length < 2) return;
    const nested = els.some((a) => els.some((b) => a !== b && a.contains(b)));
    if (!nested) duplicates.push(text.slice(0, 80));
  });
  let bullets = 0, bulletSample = '';
  d.querySelectorAll('li').forEach((li) => {
    if (!shown(li) || !li.closest('[data-sp="card-list"], [data-sp="nav"], [data-sp="header"], [data-sp="tabs"], [data-sp="list"], [data-sp="footer"], [data-sp="section"]')) return;
    const cs = w.getComputedStyle(li);
    if (cs.display === 'list-item' && cs.listStyleType !== 'none') {
      bullets += 1;
      if (!bulletSample) bulletSample = norm(li.innerText || '').slice(0, 40);
    }
  });
  const sidebars = [];
  d.querySelectorAll('[data-sp="sidebar"]').forEach((e) => { if (shown(e)) sidebars.push({width: e.getBoundingClientRect().width}); });
  return {vw: w.innerWidth, docWidth: d.documentElement.scrollWidth, cards: cards, duplicates: duplicates,
          bullets: bullets, bulletSample: bulletSample, sidebars: sidebars};
}"""


def _one_row(parts: List[Dict[str, float]]) -> bool:
    return max(p["top"] for p in parts) < min(p["bottom"] for p in parts)


def evaluate_visual(measure: Dict[str, Any], layout_applied: bool) -> List[str]:
    problems: List[str] = []
    vw = measure["vw"]
    if measure["docWidth"] > vw + OVERFLOW_TOLERANCE_PX:
        problems.append("horizontal-overflow: page is %d px wide in a %d px viewport" % (measure["docWidth"], vw))
    if measure["bullets"]:
        problems.append("bullets: %d list items still show a marker, first: %r" % (measure["bullets"], measure["bulletSample"]))
    for text in measure["duplicates"]:
        problems.append("duplicate-nodes: two visible copies of %r" % text)
    if layout_applied:
        stacked = sum(1 for card in measure["cards"] if not _one_row(card["parts"]))
        if stacked:
            problems.append("card-not-one-row: %d of %d cards stack their parts instead of one row" % (stacked, len(measure["cards"])))
        for sidebar in measure["sidebars"]:
            if sidebar["width"] >= MAX_SIDEBAR_SHARE * vw:
                problems.append("sidebar-too-wide: sidebar is %d px of a %d px viewport (limit 40%%)" % (sidebar["width"], vw))
    return problems
