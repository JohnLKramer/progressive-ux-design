---
description: Improve a styled page in a style-switcher workspace with a bounded critique-and-fix loop (render, critique, fix the top finding behind gates, keep or revert)
argument-hint: <workspace> <slug> <style...> [--doc PATH] [--max-iterations N] [--bar P0|P1|P2|P3]
---

Use the `design-refine` skill with: $ARGUMENTS

Arguments: the workspace folder, the page slug, one or more style ids (the first is the primary style), and optionally the screen doc the page came from (`--doc`), the iteration cap (`--max-iterations`, default 5) and the severity bar (`--bar`, default `P2`).

If the workspace, page or a style is missing, say so in one line and stop.
