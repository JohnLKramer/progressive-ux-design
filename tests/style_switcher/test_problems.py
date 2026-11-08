from __future__ import annotations

import pytest

from problems import Problem, ValidationError, format_problems


def test_validation_error_formats_problems():
    problems = [Problem("a", "x", "one"), Problem("b", "y", "two")]
    exc = ValidationError(problems)
    assert str(exc) == format_problems(problems)
    assert exc.problems == problems
    assert isinstance(exc, Exception)


def test_validation_error_rejects_empty_list():
    with pytest.raises(ValueError):
        ValidationError([])
