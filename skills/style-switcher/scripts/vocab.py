from __future__ import annotations

import re
from pathlib import Path
from typing import List

VOCAB_PATH = Path(__file__).resolve().parent.parent / "role-vocabulary.md"
WRAPPERS = ("shell", "content", "sidebar")

_SECTIONS = ("Roles", "Wrappers")
_BULLET = re.compile(r"^\s*-\s+`([^`]+)`")


def load_roles(path: Path = VOCAB_PATH) -> frozenset:
    names: List[str] = []
    found = {section: 0 for section in _SECTIONS}
    current = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            continue
        if current in _SECTIONS:
            match = _BULLET.match(line)
            if match:
                if match.group(1) in names:
                    raise ValueError("%s: role %r is listed twice" % (path, match.group(1)))
                names.append(match.group(1))
                found[current] += 1
    for section, count in found.items():
        if count == 0:
            raise ValueError("%s: section %r is missing or lists no roles" % (path, section))
    return frozenset(names)
