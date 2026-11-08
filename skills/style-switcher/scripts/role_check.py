"""Sanity report on `data-sp` role coverage of a page (not a gate beyond `has_shell`).

CLI: `role_check.py <page.html>` prints the report as sorted-key JSON; exit 1 with
`has_shell missing` on stderr when no element has data-sp="shell"; exit 2 on bad usage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Union

sys.path.insert(0, str(Path(__file__).resolve().parent))

import html_tree  # noqa: E402

USAGE = "usage: role_check.py <page.html>"


def coverage(page_html: Path) -> Dict[str, Union[int, bool]]:
    doc = html_tree.parse(Path(page_html).read_text(encoding="utf-8"))
    elements = list(html_tree.iter_elements(doc.body.children))
    roles = [el.get("data-sp") for el in elements]
    return {
        "roled_elements": sum(1 for role in roles if role is not None),
        "total_elements": len(elements),
        "has_shell": "shell" in roles,
        "has_content": "content" in roles,
    }


def main(argv: List[str]) -> int:
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        report = coverage(Path(argv[0]))
    except (OSError, UnicodeDecodeError) as exc:
        print("error: cannot read %s: %s" % (argv[0], getattr(exc, "strerror", None) or exc), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    if not report["has_shell"]:
        print("has_shell missing", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
