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
