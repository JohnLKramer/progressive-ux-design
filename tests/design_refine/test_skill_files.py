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
