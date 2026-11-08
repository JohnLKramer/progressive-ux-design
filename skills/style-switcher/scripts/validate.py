from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from problems import Problem, format_problems  # noqa: E402

USAGE = "usage: validate.py page <html> [--source-el-ids <file> | --source-html <src.html>] | style <dir> | manifest <path>"


def _option_value(args: List[str], name: str) -> Tuple[Optional[str], List[str]]:
    """Pop `name <value>` from args; exit 2 if the value is missing."""
    if name not in args:
        return None, args
    i = args.index(name)
    if i + 1 >= len(args):
        raise SystemExit(_usage_exit())
    return args[i + 1], args[:i] + args[i + 2:]


def _fail(message: str) -> None:
    print("error: %s" % message, file=sys.stderr)
    raise SystemExit(2)


def _run_page(args: List[str]) -> List[Problem]:
    from validate_page import collect_data_el, validate_page

    ids_file, args = _option_value(args, "--source-el-ids")
    source_html, args = _option_value(args, "--source-html")
    if len(args) != 1:
        raise SystemExit(_usage_exit())
    if ids_file is not None and source_html is not None:
        _fail("--source-el-ids and --source-html are mutually exclusive")

    source_ids: Optional[Set[str]] = None
    source_path: Optional[Path] = None
    if ids_file is not None:
        try:
            text = Path(ids_file).read_text(encoding="utf-8")
        except OSError as exc:
            _fail("cannot read --source-el-ids file %s: %s" % (ids_file, exc.strerror or exc))
        source_ids = {line.strip() for line in text.splitlines() if line.strip()}
    elif source_html is not None:
        source_path = Path(source_html)
        try:
            source_ids = collect_data_el(source_path)
        except OSError as exc:
            _fail("cannot read --source-html file %s: %s" % (source_html, exc.strerror or exc))
    problems = validate_page(Path(args[0]), source_el_ids=source_ids)
    if source_path is not None:
        from edit_check import check_edits

        problems = problems + check_edits(source_path, Path(args[0]))
    return problems


def _usage_exit() -> int:
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: List[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("page", "style", "manifest"):
        return _usage_exit()
    command, args = argv[0], argv[1:]
    if command == "manifest":
        if len(args) != 1:
            return _usage_exit()
        from manifest import validate_manifest

        try:
            problems = validate_manifest(Path(args[0]))
        except FileNotFoundError as exc:
            _fail(str(exc))
        if problems:
            print(format_problems(problems))
            return 1
        return 0
    if command == "page":
        problems = _run_page(args)
    else:
        if len(args) != 1:
            return _usage_exit()
        from validate_style import validate_style

        problems = validate_style(Path(args[0]))
    if problems:
        print(format_problems(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
