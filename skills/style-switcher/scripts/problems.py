from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Problem:
    code: str
    where: str
    message: str


def format_problems(problems: List[Problem]) -> str:
    return "\n".join("%s: %s: %s" % (p.code, p.where, p.message) for p in problems)


class ValidationError(Exception):
    def __init__(self, problems: List[Problem]) -> None:
        if not problems:
            raise ValueError("ValidationError requires at least one problem")
        super().__init__(format_problems(problems))
        self.problems = problems
