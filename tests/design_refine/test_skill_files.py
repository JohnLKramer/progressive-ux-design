import json
import re
from pathlib import Path

from ledger import FINDING_FIELDS, KINDS, LAYERS, MAX_FINDINGS, SEVERITIES, init_ledger, ingest

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "design-refine"
VERDICTS = ("better", "same", "worse")


def _json_blocks(text):
    return [json.loads(block) for block in re.findall(r"```json\n(.*?)```", text, re.S)]


def test_critic_brief_names_every_schema_field_layer_kind_severity_and_verdict():
    text = (SKILL_DIR / "critic.md").read_text()
    for name in FINDING_FIELDS + LAYERS + KINDS + SEVERITIES:
        assert "`%s`" % name in text, name
    for verdict in VERDICTS:
        assert '"%s"' % verdict in text, verdict
    assert "at most %d" % MAX_FINDINGS in text


def test_notice_credits_two_mit_sources_and_not_grapeot_text():
    text = (SKILL_DIR / "NOTICE.md").read_text()
    assert "humbleteam/design-review" in text
    assert "Prasad-D-Ware/critiquing-visual-design" in text
    assert text.count("MIT") >= 2
    grapeot_lines = [line for line in text.splitlines() if "grapeot" in line]
    assert grapeot_lines, "NOTICE must say what is not taken from grapeot/design_skill"
    for line in grapeot_lines:
        assert re.search(r"\bno text\b", line, re.I), line


def test_critic_example_review_json_passes_ingest(tmp_path):
    blocks = _json_blocks((SKILL_DIR / "critic.md").read_text())
    reviews = [b for b in blocks if isinstance(b, list)]
    assert len(reviews) == 1, "critic.md must hold exactly one example review list"
    ledger_path = tmp_path / "ledger.json"
    init_ledger(ledger_path)
    result = ingest(ledger_path, reviews[0])
    assert result["new"], "example finding should be ingested as a new open finding"


def test_critic_example_compare_json_has_a_valid_verdict():
    blocks = _json_blocks((SKILL_DIR / "critic.md").read_text())
    compares = [b for b in blocks if isinstance(b, dict)]
    assert len(compares) == 1, "critic.md must hold exactly one example compare object"
    assert set(compares[0]) == {"verdict", "reason"}
    assert compares[0]["verdict"] in VERDICTS
    assert isinstance(compares[0]["reason"], str) and compares[0]["reason"].strip()


REPO_ROOT = SKILL_DIR.parents[1]
FIXERS = ("fix-structural.md", "fix-style.md")
MARKER_ATTRS = ("data-el", "data-action", "data-exit", "data-variant")


def _repo_paths(text):
    return sorted(set(re.findall(r"`(skills/[^`\s]+\.(?:md|py|css|json|html))`", text)))


def test_fixer_briefs_state_allowed_paths_and_needs_you_escape():
    structural = (SKILL_DIR / "fix-structural.md").read_text()
    style = (SKILL_DIR / "fix-style.md").read_text()
    for text in (structural, style):
        for field in FINDING_FIELDS:
            assert "`%s`" % field in text, field
        assert "NEEDS-YOU: " in text
        assert "different approach" in text
        assert "untrusted" in text
    assert "pages/<slug>/" in structural
    assert "screen doc" in structural
    assert "NEEDS-YOU: <why>" in structural
    assert "new `data-el`" in structural
    for name in ("style.css", "layout.css", "tokens.json"):
        assert "styles/<style_id>/%s" % name in style, name
    assert "@import" in style
    assert "validate.py style" in style


def test_structural_brief_names_marker_attrs_and_build_html_path():
    text = (SKILL_DIR / "fix-structural.md").read_text()
    for attr in MARKER_ATTRS:
        assert "`%s`" % attr in text, attr
    for rel in (
        "skills/progressive-ux-design/build-html.md",
        "skills/style-switcher/make-stylable.md",
        "skills/style-switcher/role-vocabulary.md",
    ):
        assert "`%s`" % rel in text, rel
        assert (REPO_ROOT / rel).is_file(), rel
    assert "validate.py page" in text


def test_every_repo_path_in_fixer_briefs_exists():
    for name in FIXERS:
        paths = _repo_paths((SKILL_DIR / name).read_text())
        assert paths, name
        for rel in paths:
            assert (REPO_ROOT / rel).is_file(), "%s references missing %s" % (name, rel)


# --- Orchestrator: SKILL.md, command, README, plugin.json -----------------

import argparse  # noqa: E402
import shlex  # noqa: E402

import gates  # noqa: E402
import ledger  # noqa: E402
import render  # noqa: E402

SKILL_MD = SKILL_DIR / "SKILL.md"
STYLE_SWITCHER_DIR = REPO_ROOT / "skills" / "style-switcher"
SCRIPT_PARSERS = {"ledger.py": ledger._build_parser, "gates.py": gates._build_parser}
LEDGER_SUBCOMMANDS = ("init", "ingest", "next", "attempt", "status", "report")
GATES_SUBCOMMANDS = ("snapshot", "check", "restore")


def _front_matter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must open with a --- front matter block"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _fenced_blocks(text):
    return re.findall(r"```[a-z]*\n(.*?)```", text, re.S)


def _script_commands(text):
    """(script, argv, line) for every `python3 ... <dir>/scripts/<script>.py ...` line in a fenced block."""
    commands = []
    for block in _fenced_blocks(text):
        for line in block.splitlines():
            match = re.match(r"python3 (?:-I )?<skill-dir>/scripts/(ledger|gates|render)\.py(?: (.*))?$", line.strip())
            if match:
                argv = shlex.split(match.group(2) or "")
                if ">" in argv:  # shell redirect, not an argument
                    argv = argv[: argv.index(">")]
                commands.append((match.group(1) + ".py", argv, line.strip()))
    return commands


def _int_placeholders(parser, argv):
    """Replace a `<placeholder>` value with 1 where the option it belongs to is an int."""
    int_options = set()
    stack = [parser]
    while stack:
        p = stack.pop()
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                stack.extend(action.choices.values())
            elif action.type is int:
                int_options.update(action.option_strings)
    out = list(argv)
    for i, token in enumerate(out):
        if i and out[i - 1] in int_options and re.fullmatch(r"<[^>]+>", token):
            out[i] = "1"
    return out


class _Parsed(Exception):
    pass


def _render_parser_accepts(argv, monkeypatch):
    original = argparse.ArgumentParser.parse_args

    def capture(self, args=None, namespace=None):
        original(self, args, namespace)
        raise _Parsed()

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    try:
        render.main(argv)
    except _Parsed:
        return True
    except SystemExit:
        return False
    finally:
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", original)
    return False


def test_skill_md_front_matter_and_description():
    fields = _front_matter(SKILL_MD.read_text())
    assert fields.get("name") == "design-refine"
    assert fields.get("description", "").startswith("Use when"), fields.get("description")


def _resolve_mentioned_path(token):
    if token.startswith("<skill-dir>/"):
        return SKILL_DIR / token[len("<skill-dir>/"):]
    if token.startswith("<style-switcher-dir>/"):
        return STYLE_SWITCHER_DIR / token[len("<style-switcher-dir>/"):]
    if token.startswith("<") or token.startswith("/") or token.startswith("$"):
        return None  # a run-time path such as <log>/report.md
    if token.startswith("skills/"):
        return REPO_ROOT / token
    if token.endswith(".py") and "/" not in token:
        return SKILL_DIR / "scripts" / token
    return SKILL_DIR / token


def test_skill_md_commands_reference_existing_scripts_and_briefs():
    text = SKILL_MD.read_text()
    tokens = set(re.findall(r"(?<![\w./>-])((?:<[\w-]+>/)?[\w./-]*?[\w-]+\.(?:md|py))(?!\w)", text))
    checked = []
    for token in sorted(tokens):
        path = _resolve_mentioned_path(token)
        if path is None:
            continue
        checked.append(token)
        assert path.is_file(), "SKILL.md mentions %s, which resolves to missing %s" % (token, path)
    for name in ("critic.md", "fix-structural.md", "fix-style.md"):
        assert "<skill-dir>/%s" % name in text, name
    for script in ("ledger.py", "gates.py", "render.py"):
        assert "<skill-dir>/scripts/%s" % script in text, script
    assert "<style-switcher-dir>/scripts/validate.py" in text
    assert checked


def test_skill_md_script_commands_match_the_script_parsers(monkeypatch):
    commands = _script_commands(SKILL_MD.read_text())
    assert commands, "SKILL.md has no fenced script commands"
    used = {"ledger.py": set(), "gates.py": set(), "render.py": set()}
    for script, argv, line in commands:
        if script == "render.py":
            assert line.startswith("python3 <skill-dir>"), "render.py runs as plain python3: %s" % line
            assert _render_parser_accepts(argv, monkeypatch), "render.py rejects: %s" % line
            used[script].add("render")
            continue
        assert line.startswith("python3 -I "), "%s runs as python3 -I: %s" % (script, line)
        parser = SCRIPT_PARSERS[script]()
        try:
            args = parser.parse_args(_int_placeholders(parser, argv))
        except SystemExit:
            raise AssertionError("%s rejects: %s" % (script, line))
        used[script].add(args.command)
        if script == "ledger.py" and args.command == "attempt":
            assert args.result in ledger.ATTEMPT_RESULTS, line
    assert used["ledger.py"] == set(LEDGER_SUBCOMMANDS), used["ledger.py"]
    assert used["gates.py"] == set(GATES_SUBCOMMANDS), used["gates.py"]
    assert used["render.py"] == {"render"}
    results = {a[a.index("--result") + 1] for s, a, _ in commands if s == "ledger.py" and "--result" in a}
    assert results == set(ledger.ATTEMPT_RESULTS), results
    kinds = {a[a.index("--kind") + 1] for s, a, _ in commands if s == "gates.py" and "--kind" in a}
    assert kinds == {"structural", "style"}, kinds


def test_skill_md_prose_mentions_only_real_subcommands():
    text = SKILL_MD.read_text()
    for script, valid in (("ledger.py", LEDGER_SUBCOMMANDS), ("gates.py", GATES_SUBCOMMANDS)):
        for word in re.findall(r"%s ([a-z][a-z-]*)" % re.escape(script), text):
            assert word in valid, "SKILL.md uses `%s %s`, not a subcommand" % (script, word)


def test_skill_md_validate_commands_use_real_modes():
    for block in _fenced_blocks(SKILL_MD.read_text()):
        for line in block.splitlines():
            if "validate.py" in line:
                assert line.strip().startswith("python3 -I <style-switcher-dir>/scripts/validate.py "), line
                assert line.split()[3] in ("page", "style"), line


def test_readme_documents_design_refine():
    text = (REPO_ROOT / "README.md").read_text()
    assert re.search(r"^# design-refine", text, re.M | re.I), "README needs a design-refine section"
    section = text[re.search(r"^# design-refine", text, re.M | re.I).start():]
    assert "/design-refine" in section
    assert "Playwright" in section
    assert "structural" in section.lower()


def test_command_and_plugin_mention_design_refine():
    command = (REPO_ROOT / "commands" / "design-refine.md").read_text()
    fields = _front_matter(command)
    assert fields.get("description")
    assert fields.get("argument-hint")
    assert "Use the `design-refine` skill with: $ARGUMENTS" in command
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert "design-refine" in plugin["description"]
