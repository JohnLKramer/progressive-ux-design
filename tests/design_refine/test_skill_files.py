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
BRIEFS = ("critic.md",) + FIXERS
MARKER_ATTRS = ("data-el", "data-action", "data-exit", "data-variant")
BRIEF_PLACEHOLDERS = {
    "<style-switcher-dir>": REPO_ROOT / "skills" / "style-switcher",
    "<ux-skill-dir>": REPO_ROOT / "skills" / "progressive-ux-design",
}


def _brief_paths(text):
    """Every `<style-switcher-dir>/...` or `<ux-skill-dir>/...` file path in backticks, resolved against the repo."""
    found = re.findall(r"`(?:python3 -I )?(<(?:style-switcher-dir|ux-skill-dir)>)/([^`\s]+\.(?:md|py|css|json|html))", text)
    return sorted({(ph + "/" + rel, BRIEF_PLACEHOLDERS[ph] / rel) for ph, rel in found})


def _section_text(text, heading):
    start = text.index(heading)
    nxt = re.search(r"^#{1,3} ", text[start + len(heading):], re.M)
    return text[start: start + len(heading) + nxt.start()] if nxt else text[start:]


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
    mentioned = dict(_brief_paths(text))
    for token in (
        "<ux-skill-dir>/build-html.md",
        "<style-switcher-dir>/make-stylable.md",
        "<style-switcher-dir>/role-vocabulary.md",
        "<style-switcher-dir>/scripts/validate.py",
    ):
        assert token in mentioned, token
        assert mentioned[token].is_file(), token
    assert "validate.py page" in text


def test_every_skill_path_in_fixer_briefs_exists():
    for name in FIXERS:
        paths = _brief_paths((SKILL_DIR / name).read_text())
        assert paths, name
        for token, path in paths:
            assert path.is_file(), "%s references missing %s" % (name, token)


def test_briefs_have_no_bare_repo_relative_skill_paths():
    for name in BRIEFS:
        text = (SKILL_DIR / name).read_text()
        bare = re.findall(r"(?<![\w<>/.-])skills/[\w./-]+", text)
        assert not bare, "%s uses repo-relative paths %s; use <style-switcher-dir> or <ux-skill-dir>" % (name, bare)
        assert "<skill-dir>" not in text, "%s uses <skill-dir>; fixers get <style-switcher-dir>" % name


def test_structural_brief_allows_writing_the_scratch_dir_and_builds_into_it():
    text = (SKILL_DIR / "fix-structural.md").read_text()
    allowed = _section_text(text, "## Inputs")
    allowed = allowed[allowed.index("**Paths you may write**"): allowed.index("**Earlier approaches**")]
    assert "scratch directory the orchestrator gives you" in allowed
    flow = _section_text(text, "## With a screen doc")
    build = [line for line in flow.splitlines() if "build-html" in line]
    assert build and "scratch directory" in build[0], build
    assert flow.index("scratch directory") < flow.index("make-stylable")
    assert "Never write it to `ux/mockups/`" in flow
    assert "`wireframe:`" in flow and "exactly as" in flow


def test_fixer_validator_needs_you_says_the_orchestrator_restores():
    for name in FIXERS:
        text = (SKILL_DIR / name).read_text()
        assert "`NEEDS-YOU: <validator output>` and leave the files as they are; the orchestrator restores them." in text, name


# --- Orchestrator: SKILL.md, command, README, plugin.json -----------------

import argparse  # noqa: E402
import shlex  # noqa: E402

import gates  # noqa: E402
import ledger  # noqa: E402
import render  # noqa: E402

SKILL_MD = SKILL_DIR / "SKILL.md"
_PATH_PLACEHOLDER = r"<(?:skill-dir|style-switcher-dir|workspace|log|iter|doc|preflight|scratch)>"


def _plain(text):
    """SKILL.md with the single quotes around path placeholders removed, so commands compare unquoted."""
    return re.sub(r"'(%s[^'\s]*)'" % _PATH_PLACEHOLDER, r"\1", text)


def _skill_text():
    return _plain(SKILL_MD.read_text())

STYLE_SWITCHER_DIR = REPO_ROOT / "skills" / "style-switcher"
SCRIPT_PARSERS = {"ledger.py": ledger._build_parser, "gates.py": gates._build_parser}
LEDGER_SUBCOMMANDS = ("init", "ingest", "next", "attempt", "status", "report", "view")
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
    """(script, argv, line) for every `python3 ... <dir>/scripts/<script>.py ...` line in a fenced block.

    argv is tokenised with shlex, so the single-quoted path placeholders come out unquoted. `line` is the
    command with those quotes removed.
    """
    commands = []
    for block in _fenced_blocks(text):
        for line in block.splitlines():
            line = _plain(line)
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
    if token.startswith("<ux-skill-dir>/"):
        return BRIEF_PLACEHOLDERS["<ux-skill-dir>"] / token[len("<ux-skill-dir>/"):]
    if token.startswith("<") or token.startswith("/") or token.startswith("$"):
        return None  # a run-time path such as <log>/report.md
    if token.startswith("skills/"):
        return REPO_ROOT / token
    if token.endswith(".py") and "/" not in token:
        return SKILL_DIR / "scripts" / token
    return SKILL_DIR / token


def test_skill_md_commands_reference_existing_scripts_and_briefs():
    text = _skill_text()
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
    for block in _fenced_blocks(_skill_text()):
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


def _review_critic_bullet(text):
    return next(line for line in text.splitlines() if line.startswith("- **Critic, review mode.**"))


def test_review_critic_gets_the_ledger_view_not_the_ledger():
    text = _skill_text()
    bullet = _review_critic_bullet(text)
    assert "<iter>/ledger-view.json" in bullet
    assert "<log>/ledger.json" not in bullet
    assert "python3 -I <skill-dir>/scripts/ledger.py view <log>/ledger.json > <iter>/ledger-view.json" in text
    loop = _section_text(text, "## Per-style loop")
    assert loop.index("ledger.py view") < loop.index("dispatch the critic in review mode on `<iter>/before.png`")
    assert "Ledger view" in (SKILL_DIR / "critic.md").read_text()


def test_fixer_dispatch_passes_both_skill_dirs():
    text = SKILL_MD.read_text()
    fixer = next(line for line in text.splitlines() if line.startswith("- **Fixer.**"))
    assert "<style-switcher-dir>" in fixer and "<ux-skill-dir>" in fixer
    assert "`<ux-skill-dir>` is the `skills/progressive-ux-design` directory" in text


def test_preflight_renders_every_style_to_temp_before_ledger_init():
    text = _skill_text()
    preflight = _section_text(text, "## Preflight")
    renders = [line for line in _fenced_blocks(preflight) for line in line.splitlines() if "render.py" in line]
    assert renders, "Preflight must render the page"
    assert all("--out <preflight>/" in line for line in renders), renders
    assert "tempfile.mkdtemp" in preflight and "rm -rf -- <preflight>" in preflight
    assert "Exit 3" in preflight and "Playwright" in preflight
    assert text.index("render.py", text.index("## Preflight")) < text.index("scripts/ledger.py init <log>/ledger.json")
    assert text.index("## Preflight") < text.index("mkdir -p <log>")


def test_needs_you_checks_gates_before_restore():
    text = _skill_text()
    step7 = text[text.index("7. **Fix.**"): text.index("8. **Check.**")]
    needs_you = step7[step7.index("starts with `NEEDS-YOU:`"):]
    assert "gates.py check --snapshot <iter>/snapshot" in needs_you
    assert needs_you.index("gates.py check") < needs_you.index("gates.py restore")
    assert "cannot be auto-reverted" in needs_you
    assert "--result gate-failed" in needs_you


def test_finish_appends_an_iteration_log_with_screenshots():
    text = SKILL_MD.read_text()
    loop = _section_text(text, "## Per-style loop")
    assert "**Iteration log.**" in loop
    log = loop[loop.index("**Iteration log.**"):]
    for word in ("<N>", "<id>", "<fixer line>", "kept", "gate-failed", "worse",
                 "<iter>/before.png", "<iter>/after.png", "<iter>/cross-before.png", "<iter>/cross-after.png"):
        assert word in log, word
    finish = _section_text(text, "## Finish")
    assert "## Iteration log" in finish


def test_path_placeholders_in_fenced_commands_are_single_quoted():
    text = SKILL_MD.read_text()
    checked = 0
    for block in _fenced_blocks(text):
        for line in block.splitlines():
            if not line.strip().startswith(("python3", "mkdir", "rm ")) or "-I -c" in line:
                continue
            for match in re.finditer(r"(?<![\w])%s[^\s]*" % _PATH_PLACEHOLDER, line):
                start = match.start()
                assert start > 0 and line[start - 1] == "'" and match.group(0).endswith("'"), (
                    "unquoted path placeholder %r in: %s" % (match.group(0), line.strip())
                )
                checked += 1
    assert checked > 20


def test_untrusted_inputs_require_the_file_writing_tool_for_page_derived_files():
    text = SKILL_MD.read_text()
    rules = _section_text(text, "## Untrusted inputs")
    rule = next(line for line in rules.splitlines() if "file-writing tool" in line)
    assert "never through a shell command, echo or heredoc" in rule
    for word in ("critique", "iteration log", "report additions", "critic", "fixer", "page"):
        assert word in rule, word
    finish = _section_text(text, "## Finish")
    assert "file-writing tool" in finish
    assert "file-writing tool" in text[text.index("**Iteration log.**"):text.index("## Finish")]


def test_review_critic_writes_critique_json_and_replies_done_n():
    text = SKILL_MD.read_text()
    bullet = _review_critic_bullet(text)
    assert "<iter>/critique.json" in bullet and "DONE <n>" in bullet and "file-writing tool" in bullet
    step2 = text[text.index("2. **Review.**"): text.index("3. **Ingest.**")]
    assert "exactly `DONE <n>`" in step2
    assert "missing or not parseable" in step2 and "stop with the reply shown" in step2
    assert "Save it" not in step2
    critic = (SKILL_DIR / "critic.md").read_text()
    assert "DONE <n>" in critic and "`DONE 0`" in critic
    assert "file-writing tool" in critic and "Critique path" in critic
    compare = critic[critic.index("## Compare mode"):]
    assert '{"verdict"' in compare and "DONE" not in compare


def test_cross_check_stops_on_an_unrecognised_verdict():
    text = SKILL_MD.read_text()
    step9 = text[text.index("9. **Cross-check**"): text.index("10. **Render after.**")]
    assert "other than `better`, `same` or `worse` stops the run with the reply shown" in step9


def test_snapshot_step_reads_only_cross_style_and_dest():
    text = SKILL_MD.read_text()
    step6 = text[text.index("6. **Snapshot.**"): text.index("7. **Fix.**")]
    assert '{"cross_style": ..., "dest": ...}' in step6


def test_structural_brief_reuses_the_slug_so_make_stylable_step_1_is_skipped():
    text = (SKILL_DIR / "fix-structural.md").read_text()
    assert "Steps 2 to 6 apply" in text and "Steps 1 to 6" not in text
