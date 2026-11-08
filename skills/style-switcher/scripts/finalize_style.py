"""Finish a style directory: write name.txt, copy referenced assets, validate, lint.

usage: finalize_style.py <style_dir> <source> --evidence <evidence.json> [--name TEXT] [--source-dir DIR]

Every `assets/<ref>` that style.css or layout.css reaches through `url(...)`, `image-set(...)` or
`@import` is copied byte-for-byte from the source. Resolution of `<ref>`:
  (a) a reference equal to an evidence path is used as is, and copied to `assets/<that path>`;
  (b) otherwise it is matched by basename; evidence files sharing the basename must be
      byte-identical (the first sorted one is used) or the reference is ambiguous and fails.
Any other local reference (`/x`, `../x`, `x.css`, `images/x.png`) fails with `bad-asset-path`;
`./assets/x` is normalized to `assets/x`, and percent-escapes are decoded once. Remote, `data:`
and fragment-only (`url(#id)`) references are not files and are ignored here.

The files copied are listed in `assets/.finalized-assets`; a rerun deletes listed files that no CSS
references any more and never deletes anything else. A symlinked `assets/` or a symlink inside it is
refused.

name.txt: an existing name.txt is kept as is. A --name that differs from it (after stripping)
fails with `name-mismatch`; an empty or whitespace-only --name is a usage error.

After validate_style, lint_style checks the style for authoring mistakes; its problems are
raised in the same ValidationError.
"""
from __future__ import annotations

import filecmp
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gather_evidence import _scrub  # noqa: E402
from problems import Problem, ValidationError, format_problems  # noqa: E402
from unpack import UnpackError, source_name  # noqa: E402
from validate_style import _COMMENT, validate_style  # noqa: E402
from vocab import WRAPPERS, load_roles  # noqa: E402

USAGE = ("usage: finalize_style.py <style_dir> <source> --evidence <evidence.json> "
         "[--name TEXT] [--source-dir DIR]")
MANIFEST = ".finalized-assets"
_SKIP_PREFIXES = ("http:", "https:", "//", "data:")
_CSS_FILES = ("style.css", "layout.css")


# ---- references -------------------------------------------------------------------------

_TOKEN = re.compile(r"url\(|image-set\(|@import", re.IGNORECASE)
_IMAGE_SET_TOKEN = re.compile(r"[()\"']|url\(", re.IGNORECASE)
_STRING_STOP = {'"': re.compile(r'["\\\n]'), "'": re.compile(r"['\\\n]")}
_SPACE = re.compile(r"\s*")


def _read_string(css: str, pos: int) -> Tuple[str, int]:
    """(value, index past the string) for the string opened at css[pos]; unclosed ends at newline."""
    stop = _STRING_STOP[css[pos]]
    out: List[str] = []
    i = pos + 1
    while True:
        match = stop.search(css, i)
        if match is None:
            out.append(css[i:])
            return "".join(out), len(css)
        out.append(css[i:match.start()])
        found = match.group()
        if found == "\\":
            out.append(css[match.end():match.end() + 1])
            i = match.end() + 1
        elif found == "\n":
            return "".join(out), match.start()
        else:
            return "".join(out), match.end()


def _read_url(css: str, pos: int) -> Tuple[str, int]:
    """(value, index past `)`) for a url( whose argument starts at pos."""
    pos = _SPACE.match(css, pos).end()
    if pos < len(css) and css[pos] in "\"'":
        value, pos = _read_string(css, pos)
        close = css.find(")", pos)
        return value, (len(css) if close < 0 else close + 1)
    close = css.find(")", pos)
    if close < 0:
        return css[pos:].strip(), len(css)
    return css[pos:close].strip(), close + 1


def _read_image_set(css: str, pos: int) -> Tuple[List[str], int]:
    values: List[str] = []
    depth = 1
    while depth:
        match = _IMAGE_SET_TOKEN.search(css, pos)
        if match is None:
            return values, len(css)
        token = match.group()
        if token in ('"', "'"):
            value, pos = _read_string(css, match.start())
            values.append(value)
        elif token == "(":
            depth += 1
            pos = match.end()
        elif token == ")":
            depth -= 1
            pos = match.end()
        else:
            value, pos = _read_url(css, match.end())
            values.append(value)
    return values, pos


def _raw_references(css: str) -> List[str]:
    found: List[str] = []
    pos = 0
    while True:
        match = _TOKEN.search(css, pos)
        if match is None:
            return found
        token = match.group().lower()
        pos = match.end()
        if token == "url(":
            value, pos = _read_url(css, pos)
            found.append(value)
        elif token == "image-set(":
            values, pos = _read_image_set(css, pos)
            found.extend(values)
        else:
            quote_at = _SPACE.match(css, pos).end()
            if quote_at < len(css) and css[quote_at] in "\"'":
                value, pos = _read_string(css, quote_at)
                found.append(value)


def _normalize(raw: str) -> Optional[str]:
    """`assets/<rel>` for a local reference, None when it is not a file, ValueError when it is bad."""
    value = raw.strip()
    if value.lower().startswith(_SKIP_PREFIXES) or value.startswith("#"):
        return None
    value = value.split("#", 1)[0].split("?", 1)[0]
    if not value:
        raise ValueError("empty url() reference")
    value = unquote(value)
    while value.startswith("./"):
        value = value[2:]
    if not value.startswith("assets/") or value == "assets/":
        raise ValueError("local reference must be assets/<file> (got %s)" % raw.strip())
    return value


def _references(style_dir: Path) -> Tuple[List[Tuple[str, str]], List[Problem]]:
    """(css file name, normalized assets/ reference), de-duplicated in order, and bad references."""
    found: List[Tuple[str, str]] = []
    problems: List[Problem] = []
    for name in _CSS_FILES:
        path = style_dir / name
        if not path.is_file():
            continue
        css = _COMMENT.sub(" ", path.read_text(encoding="utf-8"))
        for raw in _raw_references(css):
            try:
                value = _normalize(raw)
            except ValueError as exc:
                problems.append(Problem("bad-asset-path", name, str(exc)))
                continue
            if value is not None and (name, value) not in found:
                found.append((name, value))
    by_lower: Dict[str, Set[str]] = {}
    for _, value in found:
        by_lower.setdefault(value.lower(), set()).add(value)
    for variants in by_lower.values():
        if len(variants) > 1:
            problems.append(Problem("bad-asset-path", "assets",
                                    "references differ only by case: %s" % ", ".join(sorted(variants))))
    return found, problems


# ---- asset planning ---------------------------------------------------------------------


def _is_under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _evidence_paths(evidence_assets: dict) -> List[str]:
    try:
        return list(evidence_assets["fonts"]) + list(evidence_assets["images"])
    except (KeyError, TypeError) as exc:
        raise ValidationError([Problem("missing-file", "evidence", "assets need `fonts` and `images` lists")]) from exc


def _truncation_note(assets_truncated: Optional[dict]) -> str:
    if assets_truncated is None:
        return ""
    if not isinstance(assets_truncated, dict):
        raise ValueError("assets_truncated must be an object")
    counts = {k: v for k, v in assets_truncated.items() if isinstance(v, int) and v > 0}
    if not counts:
        return ""
    detail = ", ".join("%s: %d" % (k, counts[k]) for k in sorted(counts))
    return ("; the evidence asset lists were truncated (%s omitted), so the file may exist "
            "in the source but be unlisted" % detail)


def _source_problem(where: str, reference: str, rel: str, root: Path) -> Tuple[Optional[Path], Optional[Problem]]:
    if ".." in rel.split("/"):
        return None, Problem("bad-asset-path", where, "%s resolves outside the source directory" % reference)
    resolved = (root / rel).resolve()
    if not _is_under(resolved, root):
        return None, Problem("bad-asset-path", where, "%s resolves outside the source directory" % reference)
    if not resolved.is_file():
        return None, Problem("missing-file", where, "%s: source file %s does not exist" % (reference, rel))
    return resolved, None


def _plan_copy(where: str, reference: str, listed: List[str], root: Path, style_assets: Path,
               note: str) -> Tuple[Optional[Tuple[Path, Path, str]], Optional[Problem]]:
    rel = reference[len("assets/"):]
    parts = rel.split("/")
    if (".." in parts or "." in parts or "" in parts or "\\" in rel or "\x00" in rel
            or parts[-1] == MANIFEST):
        return None, Problem("bad-asset-path", where, "unsafe asset reference: %s" % reference)
    if rel in listed:
        candidates = [rel]
    else:
        candidates = sorted({p for p in listed if p.rsplit("/", 1)[-1] == parts[-1]})
    if not candidates:
        return None, Problem("missing-file", where,
                             "%s is not in the evidence asset list%s" % (reference, note))
    sources: List[Path] = []
    for candidate in candidates:
        resolved, problem = _source_problem(where, reference, candidate, root)
        if problem:
            return None, problem
        sources.append(resolved)  # type: ignore[arg-type]
    if any(not filecmp.cmp(str(sources[0]), str(other), shallow=False) for other in sources[1:]):
        return None, Problem("missing-file", where,
                             "%s is ambiguous: write the reference as assets/<one of: %s>"
                             % (reference, ", ".join(candidates)))
    dest = style_assets.joinpath(*parts)
    if not _is_under(dest.resolve(), style_assets.resolve()):
        return None, Problem("bad-asset-path", where, "%s would be written outside assets/" % reference)
    return (sources[0], dest, rel), None


# ---- assets directory state -------------------------------------------------------------


def _check_assets_dir(assets: Path) -> List[Problem]:
    if assets.is_symlink():
        return [Problem("bad-asset-path", str(assets), "assets/ is a symlink; refusing to write through it")]
    if not assets.exists():
        return []
    if not assets.is_dir():
        return [Problem("bad-asset-path", str(assets), "assets exists and is not a directory")]
    problems: List[Problem] = []
    for dirpath, dirnames, filenames in os.walk(str(assets)):
        for entry in dirnames + filenames:
            full = os.path.join(dirpath, entry)
            if os.path.islink(full):
                problems.append(Problem("bad-asset-path", full, "symlinks inside assets/ are refused"))
    return problems


def _read_manifest(assets: Path) -> Tuple[List[str], List[Problem]]:
    manifest = assets / MANIFEST
    if not manifest.is_file() or manifest.is_symlink():
        return [], []
    entries: List[str] = []
    problems: List[Problem] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry:
            continue
        parts = entry.split("/")
        if (entry.startswith("/") or ".." in parts or "." in parts or "" in parts or "\\" in entry
                or "\x00" in entry or entry == MANIFEST
                or not _is_under(assets.joinpath(*parts).resolve(), assets.resolve())):
            problems.append(Problem("bad-asset-path", str(manifest), "unsafe manifest entry: %s" % entry))
        else:
            entries.append(entry)
    return entries, problems


def _remove_stale(assets: Path, stale: Iterable[str]) -> None:
    root = assets.resolve()
    for rel in sorted(stale):
        target = assets.joinpath(*rel.split("/"))
        if target.is_file() and not target.is_symlink():
            target.unlink()
        parent = target.parent
        while parent != assets and parent.is_dir() and _is_under(parent.resolve(), root) \
                and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def _write_manifest(assets: Path, copied: List[str]) -> None:
    manifest = assets / MANIFEST
    if copied:
        manifest.write_text("".join(rel + "\n" for rel in sorted(copied)), encoding="utf-8")
    elif manifest.exists():
        manifest.unlink()
    if assets.is_dir() and not any(assets.iterdir()):
        assets.rmdir()


# ---- finalize ---------------------------------------------------------------------------


def _check_name(style_dir: Path, source: Path, name: Optional[str]) -> None:
    if name is not None and not name.strip():
        raise ValueError("name must not be empty or whitespace-only")
    name_file = style_dir / "name.txt"
    if name_file.exists() or name_file.is_symlink():
        if name is None:
            return
        existing = name_file.read_text(encoding="utf-8").strip()
        if existing != name.strip():
            raise ValidationError([Problem(
                "name-mismatch", str(name_file),
                "name.txt says %r but --name is %r; edit or delete name.txt to rename"
                % (existing, name.strip()))])
        return
    text = (name if name is not None else source_name(source)).strip()
    if not text:
        raise ValueError("style name must not be empty")
    name_file.write_text(text + "\n", encoding="utf-8")


def finalize_style(style_dir: Path, source: Path, evidence_assets: dict,
                   name: Optional[str] = None, source_dir: Optional[Path] = None,
                   assets_truncated: Optional[dict] = None) -> None:
    """Write name.txt, copy referenced assets, then validate_style and lint_style.

    An existing name.txt is kept; a differing `name` raises Problem `name-mismatch`. An empty
    `name` raises ValueError. `assets_truncated` is the evidence's `assets_truncated` counts.
    """
    style_dir, source = Path(style_dir), Path(source)
    _check_name(style_dir, source, name)

    assets = style_dir / "assets"
    references, problems = _references(style_dir)
    problems.extend(_check_assets_dir(assets))
    previous, manifest_problems = _read_manifest(assets)
    problems.extend(manifest_problems)

    plans: List[Tuple[Path, Path, str]] = []
    if references:
        search = Path(source_dir) if source_dir is not None else (source if source.is_dir() else None)
        if search is None:
            raise ValidationError(problems + [Problem(
                "missing-file", str(source),
                "style references %s but source is not a directory; pass the unpacked source_dir"
                % references[0][1])])
        root = search.resolve()
        listed = _evidence_paths(evidence_assets)
        note = _truncation_note(assets_truncated)
        for where, reference in references:
            plan, problem = _plan_copy(where, reference, listed, root, assets, note)
            if problem:
                problems.append(problem)
            elif plan:
                plans.append(plan)
        by_lower: Dict[str, Set[str]] = {}
        for _, _, rel in plans:
            by_lower.setdefault(rel.lower(), set()).add(rel)
        for variants in by_lower.values():
            if len(variants) > 1:
                problems.append(Problem("bad-asset-path", "assets",
                                        "copies would collide case-insensitively: %s" % ", ".join(sorted(variants))))
    if problems:
        raise ValidationError(problems)

    copied: List[str] = []
    for src_file, dest, rel in plans:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_file, dest)
        if rel not in copied:
            copied.append(rel)
    if copied or previous:
        _remove_stale(assets, set(previous) - set(copied))
        _write_manifest(assets, copied)

    problems = validate_style(style_dir) + lint_style(style_dir)
    if problems:
        raise ValidationError(problems)


# ---- lint_style -------------------------------------------------------------------------

_GROUP_AT_RULES = ("@media", "@supports", "@layer", "@container", "@document", "@scope", "@starting-style")
_PROPERTY = re.compile(r"-{0,2}[A-Za-z_][\w-]*")
_AT_NAME = re.compile(r"@[\w-]+")
_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*([,)])?", re.IGNORECASE)
_DECLARED = re.compile(r"(?<![\w-])(--[\w-]+)\s*:")
_ROLE_SELECTOR = re.compile(r"\[\s*data-sp\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([\w-]+))\s*\]")
_BRACES = re.compile(r"[{};]")
_SIZE_OK = ("auto", "100%", "max-content", "fit-content")
_BARE_SELECTORS = ("svg", "img", "*")
_TOKEN_VARS = (("palette", "--color-"), ("fonts", "--font-"), ("scale", "--size-"),
               ("spacing", "--space-"), ("radii", "--radius-"), ("shadows", "--shadow-"))


class _Rule:
    def __init__(self, selector: str) -> None:
        self.selector = selector
        self.decls: List[Tuple[str, str]] = []


def _declaration(chunk: str) -> Optional[Tuple[str, str]]:
    colon = chunk.find(":")
    if colon < 1:
        return None
    prop = chunk[:colon].strip()
    if not _PROPERTY.fullmatch(prop):
        return None
    value = chunk[colon + 1:].strip()
    if value.lower().endswith("important"):
        rest = value[:-len("important")].rstrip()
        if rest.endswith("!"):
            value = rest[:-1].rstrip()
    return (prop if prop.startswith("--") else prop.lower()), value


def _kind(prelude: str, parent: str) -> str:
    if parent == "skip":
        return "skip"
    prelude = prelude.strip()
    if prelude.startswith("@"):
        match = _AT_NAME.match(prelude)
        name = match.group().lower() if match else ""
        return "group" if name in _GROUP_AT_RULES else "skip"
    return "rule"


def _parse_rules(css: str) -> Tuple[str, List[_Rule]]:
    """(scrubbed css, rules). Tolerant and linear; @font-face/@keyframes bodies are skipped, @media descended."""
    text = _scrub(css)
    rules: List[_Rule] = []
    stack: List[Tuple[str, Optional[_Rule]]] = []
    last = 0

    def add(chunk: str) -> None:
        if stack and stack[-1][0] == "rule":
            decl = _declaration(chunk)
            if decl:
                stack[-1][1].decls.append(decl)  # type: ignore[union-attr]

    for match in _BRACES.finditer(text):
        pos = match.start()
        chunk = text[last:pos]
        last = pos + 1
        token = match.group()
        if token == ";":
            add(chunk)
        elif token == "{":
            parent = stack[-1][0] if stack else "group"
            decls, _, prelude = chunk.rpartition(";") if parent == "rule" else ("", "", chunk)
            add(decls)
            kind = _kind(prelude, parent)
            rule = None
            if kind == "rule":
                rule = _Rule(" ".join(prelude.split()))
                rules.append(rule)
            stack.append((kind, rule))
        elif stack:
            add(chunk)
            stack.pop()
    add(text[last:])
    return text, rules


def _split_commas(selector: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    quote = ""
    start = 0
    for i, ch in enumerate(selector):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(selector[start:i].strip())
            start = i + 1
    parts.append(selector[start:].strip())
    return parts


def _norm(value: str) -> str:
    return " ".join(value.lower().split())


def _lint_rules(where: str, rules: List[_Rule]) -> List[Problem]:
    problems: List[Problem] = []
    for rule in rules:
        parts = [_norm(p) for p in _split_commas(rule.selector)]
        bare = [p for p in parts if p in _BARE_SELECTORS]
        hides_ok = rule.selector.replace(" ", "").lower() == "[hidden]"
        for prop, value in rule.decls:
            lowered = _norm(value)
            if bare and prop in ("width", "height") and lowered not in _SIZE_OK:
                problems.append(Problem(
                    "svg-global-size", where,
                    "`%s` sets `%s: %s` for every icon/image; scope it (e.g. `nav svg`) or use max-%s"
                    % (bare[0], prop, value, prop)))
            if not hides_ok and ((prop == "display" and lowered == "none")
                                 or (prop == "visibility" and lowered == "hidden")):
                problems.append(Problem(
                    "style-hides", where,
                    "`%s` declares `%s: %s`; a style may only hide `[hidden]`" % (rule.selector, prop, value)))
    return problems


_HIDDEN_RULE = re.compile(r"(?:^|[};\s])\[\s*hidden\s*\]\s*\{[^{}]*display\s*:\s*none\s*!\s*important", re.IGNORECASE)


def _lint_hidden_rule(css_path: Path, text: str) -> List[Problem]:
    """A page hides copies with `hidden`; layout.css rules such as `display: flex` beat the browser default unless the style says `!important`."""
    if _HIDDEN_RULE.search(text):
        return []
    return [Problem("hidden-rule", str(css_path), "no `[hidden] { display: none !important; }` rule; hidden copies would show")]


def _lint_vars(texts: Dict[str, str]) -> List[Problem]:
    declared: Set[str] = set()
    for text in texts.values():
        declared.update(_DECLARED.findall(text))
    problems: List[Problem] = []
    for where, text in texts.items():
        reported: Set[str] = set()
        for match in _VAR.finditer(text):
            var = match.group(1)
            if match.group(2) != "," and var not in declared and var not in reported:
                reported.add(var)
                problems.append(Problem("undefined-var", where, "var(%s) has no `%s:` declaration" % (var, var)))
    return problems


def _token_strings(value: object, path: str) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    stack: List[Tuple[object, str]] = [(value, path)]
    while stack:
        item, where = stack.pop()
        if isinstance(item, str):
            found.append((where, item))
        elif isinstance(item, dict):
            stack.extend((v, "%s.%s" % (where, k)) for k, v in item.items())
        elif isinstance(item, list):
            stack.extend((v, "%s[%d]" % (where, i)) for i, v in enumerate(item))
    return found


def _lint_tokens(tokens_path: Path, css_path: Path, rules: Optional[List[_Rule]]) -> List[Problem]:
    try:
        tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []  # validate_style reports bad-tokens
    if not isinstance(tokens, dict):
        return []
    problems: List[Problem] = []
    for where, text in _token_strings(tokens, "tokens"):
        if "var(" in text:
            problems.append(Problem("token-var", str(tokens_path), "%s contains var(): %s" % (where, text)))
    if rules is None:
        return problems
    root: Dict[str, Set[str]] = {}
    for rule in rules:
        if any(p.lower() == ":root" for p in _split_commas(rule.selector)):
            for prop, value in rule.decls:
                if prop.startswith("--"):
                    root.setdefault(prop, set()).add(_norm(value))
    for section, prefix in _TOKEN_VARS:
        entries = tokens.get(section)
        if not isinstance(entries, dict):
            continue
        for key, value in entries.items():
            var = prefix + str(key)
            if not isinstance(value, str):
                problems.append(Problem("token-mismatch", str(tokens_path),
                                        "%s.%s must be a string to match :root %s" % (section, key, var)))
            elif var not in root:
                problems.append(Problem("token-mismatch", str(css_path),
                                        "%s.%s: :root has no %s (tokens.json says %s)" % (section, key, var, value)))
            elif _norm(value) not in root[var]:
                problems.append(Problem("token-mismatch", str(css_path),
                                        "%s.%s: :root %s differs from tokens.json value %s"
                                        % (section, key, var, value)))
    return problems


def _lint_roles(css_path: Path, rules: List[_Rule]) -> List[Problem]:
    present: Set[str] = set()
    for rule in rules:
        for match in _ROLE_SELECTOR.finditer(rule.selector):
            present.add(next(g for g in match.groups() if g is not None))
    return [Problem("role-rule-missing", str(css_path), 'no [data-sp="%s"] rule' % role)
            for role in sorted(load_roles() | set(WRAPPERS)) if role not in present]


def lint_style(style_dir: Path) -> List[Problem]:
    """Authoring mistakes in a style directory. Missing files are validate_style's to report."""
    style_dir = Path(style_dir)
    css_path, tokens_path = style_dir / "style.css", style_dir / "tokens.json"
    problems: List[Problem] = []
    texts: Dict[str, str] = {}
    rules: Optional[List[_Rule]] = None
    for name in _CSS_FILES:
        path = style_dir / name
        if not path.is_file():
            continue
        text, parsed = _parse_rules(path.read_text(encoding="utf-8"))
        texts[str(path)] = text
        if name == "style.css":
            rules = parsed
    if rules is not None:
        problems.extend(_lint_rules(str(css_path), rules))
        problems.extend(_lint_roles(css_path, rules))
        problems.extend(_lint_hidden_rule(css_path, texts[str(css_path)]))
    problems.extend(_lint_vars(texts))
    if tokens_path.is_file():
        problems.extend(_lint_tokens(tokens_path, css_path, rules))
    return problems


# ---- cli --------------------------------------------------------------------------------


def _parse(args: List[str]) -> Optional[Dict[str, object]]:
    values: Dict[str, str] = {}
    positional: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--evidence", "--name", "--source-dir"):
            if i + 1 >= len(args) or arg in values:
                return None
            values[arg] = args[i + 1]
            i += 2
        elif arg.startswith("--"):
            return None
        else:
            positional.append(arg)
            i += 1
    if len(positional) != 2 or "--evidence" not in values:
        return None
    if "--name" in values and not values["--name"].strip():
        return None
    return {"positional": positional, **values}


def main(argv: List[str]) -> int:
    parsed = _parse(list(argv))
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    style_dir, source = (Path(p) for p in parsed["positional"])  # type: ignore[union-attr]
    try:
        with open(str(parsed["--evidence"]), encoding="utf-8") as handle:
            evidence = json.load(handle)
        assets = evidence["assets"]
        source_dir = Path(str(parsed["--source-dir"])) if "--source-dir" in parsed else None
        finalize_style(style_dir, source, assets, name=parsed.get("--name"),  # type: ignore[arg-type]
                       source_dir=source_dir, assets_truncated=evidence.get("assets_truncated"))
    except ValidationError as exc:
        print(format_problems(exc.problems), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, UnpackError) as exc:
        print("error: %s" % str(exc).replace("\n", " "), file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
