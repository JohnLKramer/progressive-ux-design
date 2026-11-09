import json

import pytest

import ledger
from ledger import LedgerError, ingest, init_ledger, load_ledger, next_finding, record_attempt, report, status


def finding(**over):
    base = {
        "same_as": "new",
        "title": "Cancel is the loudest button",
        "layer": "STRUCTURAL",
        "severity": "P1",
        "kind": "execution",
        "before": "Cancel is filled and larger than Book",
        "after": "Book is the primary action",
        "why": "Nielsen: aesthetic and minimalist design",
        "fixer_instruction": "Make Cancel a quiet secondary action.",
    }
    base.update(over)
    return base


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "ledger.json"
    init_ledger(p)
    return p


def raw(path):
    return path.read_text()


def set_status(path, fid, status, attempts=0):
    data = json.loads(path.read_text())
    data["findings"][fid]["status"] = status
    data["findings"][fid]["attempts"] = attempts
    path.write_text(json.dumps(data))


def test_init_writes_version_1_and_defaults(tmp_path):
    p = tmp_path / "sub" / "ledger.json"
    result = init_ledger(p)
    assert result == json.loads(p.read_text())
    assert result == {
        "version": 1,
        "max_iterations": 5,
        "bar": "P2",
        "findings": {},
        "history": [],
        "total_attempts": 0,
    }


def test_init_accepts_custom_values(tmp_path):
    result = init_ledger(tmp_path / "l.json", max_iterations=3, bar="P1")
    assert result["max_iterations"] == 3 and result["bar"] == "P1"


def test_init_rejects_bad_bar_and_existing_file(tmp_path, path):
    with pytest.raises(LedgerError):
        init_ledger(tmp_path / "x.json", bar="P9")
    with pytest.raises(LedgerError):
        init_ledger(path)


def test_load_rejects_missing_file_and_wrong_version(tmp_path):
    with pytest.raises(LedgerError) as e:
        load_ledger(tmp_path / "nope.json")
    assert e.value.problems
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"version": 2}))
    with pytest.raises(LedgerError):
        load_ledger(p)


def test_ingest_assigns_sequential_ids(path):
    result = ingest(path, [finding(), finding(title="Footer crushed")])
    assert result["new"] == ["F1", "F2"]
    data = load_ledger(path)
    f1 = data["findings"]["F1"]
    assert f1["id"] == "F1" and f1["status"] == "open"
    assert f1["attempts"] == 0 and f1["approaches"] == []
    assert "same_as" not in f1
    assert f1["title"] == "Cancel is the loudest button"
    assert data["history"] == [2]
    again = ingest(path, [finding(same_as="F1"), finding(same_as="F2"), finding(title="third")])
    assert again["new"] == ["F3"]


def test_ingest_rejects_unknown_field(path):
    before = raw(path)
    with pytest.raises(LedgerError) as e:
        ingest(path, [finding(color="red")])
    assert any("color" in p.message for p in e.value.problems)
    assert raw(path) == before


def test_ingest_rejects_missing_field_and_bad_enums(path):
    bad = finding()
    del bad["why"]
    with pytest.raises(LedgerError):
        ingest(path, [bad])
    for over in ({"severity": "P4"}, {"layer": "CSS"}, {"kind": "taste"}, {"title": ""}):
        with pytest.raises(LedgerError):
            ingest(path, [finding(**over)])


def test_ingest_collects_all_problems(path):
    with pytest.raises(LedgerError) as e:
        ingest(path, [finding(severity="P9"), finding(layer="nope")])
    assert len(e.value.problems) == 2


def test_ingest_rejects_more_than_8_findings(path):
    with pytest.raises(LedgerError):
        ingest(path, [finding(title="t%d" % i) for i in range(9)])
    assert ingest(path, [finding(title="t%d" % i) for i in range(8)])["new"][-1] == "F8"


def test_ingest_rejects_non_list_critique(path):
    with pytest.raises(LedgerError):
        ingest(path, {"findings": []})  # type: ignore[arg-type]


def test_ingest_rejects_unknown_same_as_and_leaves_file_unchanged(path):
    ingest(path, [finding()])
    before = raw(path)
    with pytest.raises(LedgerError):
        ingest(path, [finding(same_as="F1"), finding(same_as="F99")])
    assert raw(path) == before


def test_ingest_rejects_same_id_twice(path):
    ingest(path, [finding()])
    with pytest.raises(LedgerError):
        ingest(path, [finding(same_as="F1"), finding(same_as="F1")])


def test_preference_is_dropped(path):
    result = ingest(path, [finding(kind="preference")])
    assert result["dropped"] == ["F1"] and result["new"] == []
    data = load_ledger(path)
    assert data["findings"]["F1"]["status"] == "dropped"
    assert data["history"] == [0]


def test_intent_and_ambiguous_go_to_needs_you(path):
    result = ingest(path, [finding(kind="intent"), finding(layer="AMBIGUOUS", title="x")])
    assert result["needs_you"] == ["F1", "F2"]
    assert result["new"] == []
    data = load_ledger(path)
    assert data["findings"]["F1"]["status"] == "needs_you"
    assert data["history"] == [0]


def test_empty_critique_is_accepted(path):
    result = ingest(path, [])
    assert result == {"new": [], "matched": [], "fixed": [], "unresolved": [], "needs_you": [], "dropped": []}
    assert load_ledger(path)["history"] == [0]


def test_history_counts_only_findings_at_or_above_bar(path):
    ingest(path, [finding(severity="P1"), finding(severity="P3", title="low")])
    assert load_ledger(path)["history"] == [1]


def test_matched_finding_updates_text_and_reports_matched(path):
    ingest(path, [finding()])
    result = ingest(path, [finding(same_as="F1", before="new evidence", severity="P0")])
    assert result["matched"] == ["F1"] and result["new"] == []
    f = load_ledger(path)["findings"]["F1"]
    assert f["before"] == "new evidence" and f["severity"] == "P0" and f["status"] == "open"


def test_attempted_finding_not_reraised_becomes_fixed(path):
    ingest(path, [finding()])
    set_status(path, "F1", "attempted", 1)
    result = ingest(path, [])
    assert result["fixed"] == ["F1"]
    assert load_ledger(path)["findings"]["F1"]["status"] == "fixed"


def test_unmentioned_open_finding_becomes_dropped(path):
    ingest(path, [finding()])
    result = ingest(path, [])
    assert result["dropped"] == ["F1"]
    assert load_ledger(path)["findings"]["F1"]["status"] == "dropped"


def test_unmentioned_retry_becomes_dropped(path):
    ingest(path, [finding()])
    set_status(path, "F1", "retry", 1)
    assert ingest(path, [])["dropped"] == ["F1"]


def test_unmentioned_unresolved_and_needs_you_unchanged(path):
    ingest(path, [finding(), finding(kind="intent", title="b")])
    set_status(path, "F1", "unresolved", 2)
    result = ingest(path, [])
    assert result["dropped"] == [] and result["fixed"] == []
    data = load_ledger(path)
    assert data["findings"]["F1"]["status"] == "unresolved"
    assert data["findings"]["F2"]["status"] == "needs_you"


def test_reraised_attempted_finding_becomes_retry_after_one_attempt_and_unresolved_after_two(path):
    ingest(path, [finding()])
    set_status(path, "F1", "attempted", 1)
    result = ingest(path, [finding(same_as="F1")])
    assert result["matched"] == ["F1"] and result["unresolved"] == []
    assert load_ledger(path)["findings"]["F1"]["status"] == "retry"

    set_status(path, "F1", "attempted", 2)
    result = ingest(path, [finding(same_as="F1")])
    assert result["unresolved"] == ["F1"]
    assert load_ledger(path)["findings"]["F1"]["status"] == "unresolved"


def test_reraised_unresolved_stays_unresolved(path):
    ingest(path, [finding()])
    set_status(path, "F1", "unresolved", 2)
    ingest(path, [finding(same_as="F1")])
    f = load_ledger(path)["findings"]["F1"]
    assert f["status"] == "unresolved" and f["attempts"] == 2


def test_reraised_fixed_reopens(path):
    ingest(path, [finding()])
    set_status(path, "F1", "fixed", 1)
    result = ingest(path, [finding(same_as="F1")])
    assert result["matched"] == ["F1"]
    f = load_ledger(path)["findings"]["F1"]
    assert f["status"] == "open" and f["attempts"] == 1


def test_reraised_retry_stays_retry_and_keeps_approaches(path):
    ingest(path, [finding()])
    data = json.loads(path.read_text())
    data["findings"]["F1"].update(status="retry", attempts=1, approaches=["tried A"])
    path.write_text(json.dumps(data))
    ingest(path, [finding(same_as="F1")])
    f = load_ledger(path)["findings"]["F1"]
    assert f["status"] == "retry" and f["approaches"] == ["tried A"]


def test_reraised_as_preference_is_dropped(path):
    ingest(path, [finding()])
    result = ingest(path, [finding(same_as="F1", kind="preference")])
    assert result["dropped"] == ["F1"]
    assert load_ledger(path)["findings"]["F1"]["status"] == "dropped"


def test_ingest_does_not_touch_other_ledger_fields(path):
    ingest(path, [finding()])
    data = load_ledger(path)
    assert data["total_attempts"] == 0 and data["max_iterations"] == 5 and data["bar"] == "P2"


def test_no_temp_files_left_behind(path):
    ingest(path, [finding()])
    assert [p.name for p in path.parent.iterdir()] == ["ledger.json"]


def test_constants():
    assert ledger.KINDS == ("execution", "intent", "preference")
    assert ledger.MAX_FINDINGS == 8
    assert ledger.SEVERITIES == ("P0", "P1", "P2", "P3")
    assert ledger.LAYERS == ("STRUCTURAL", "STYLE-ONLY", "AMBIGUOUS")
    assert ledger.FINDING_FIELDS[0] == "same_as"


def test_next_prefers_severity_then_structural_then_id(path):
    ingest(path, [
        finding(title="a", severity="P1", layer="STYLE-ONLY"),
        finding(title="b", severity="P1", layer="STRUCTURAL"),
        finding(title="c", severity="P0", layer="STYLE-ONLY"),
        finding(title="d", severity="P1", layer="STRUCTURAL"),
    ])
    data = load_ledger(path)
    assert next_finding(data)["id"] == "F3"
    data["findings"]["F3"]["status"] = "fixed"
    assert next_finding(data)["id"] == "F2"
    data["findings"]["F2"]["status"] = "fixed"
    assert next_finding(data)["id"] == "F4"
    data["findings"]["F4"]["status"] = "fixed"
    assert next_finding(data)["id"] == "F1"


def test_next_orders_ids_numerically(path):
    ingest(path, [finding(title="t%d" % i) for i in range(8)])
    ingest(path, [finding(same_as="F%d" % i, title="t") for i in range(1, 9)] + [])
    data = load_ledger(path)
    for fid in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"):
        data["findings"][fid]["status"] = "fixed"
    data["findings"]["F10"] = dict(data["findings"]["F2"], id="F10", status="open")
    data["findings"]["F9"] = dict(data["findings"]["F2"], id="F9", status="open")
    assert next_finding(data)["id"] == "F9"


def test_next_skips_below_bar_and_non_open(path):
    ingest(path, [
        finding(title="low", severity="P3"),
        finding(title="done"),
        finding(title="waiting"),
    ])
    set_status(path, "F2", "attempted", 1)
    set_status(path, "F3", "unresolved", 2)
    assert next_finding(load_ledger(path)) is None
    set_status(path, "F3", "retry", 1)
    assert next_finding(load_ledger(path))["id"] == "F3"


def test_first_failed_attempt_sets_retry_second_sets_unresolved(path):
    ingest(path, [finding()])
    entry = record_attempt(path, "F1", "made cancel quiet", "gate-failed")
    assert entry["status"] == "retry" and entry["attempts"] == 1
    entry = record_attempt(path, "F1", "removed cancel", "worse")
    assert entry["status"] == "unresolved" and entry["attempts"] == 2
    data = load_ledger(path)
    assert data["findings"]["F1"]["approaches"] == ["made cancel quiet", "removed cancel"]
    assert data["total_attempts"] == 2


def test_kept_attempt_sets_attempted(path):
    ingest(path, [finding()])
    entry = record_attempt(path, "F1", "made cancel quiet", "kept")
    assert entry["status"] == "attempted" and entry["attempts"] == 1
    assert load_ledger(path)["total_attempts"] == 1


def test_record_attempt_rejects_bad_input_and_leaves_file_unchanged(path):
    ingest(path, [finding(), finding(title="b")])
    set_status(path, "F2", "fixed", 1)
    before = raw(path)
    with pytest.raises(LedgerError):
        record_attempt(path, "F9", "x", "kept")
    with pytest.raises(LedgerError):
        record_attempt(path, "F2", "x", "kept")
    with pytest.raises(LedgerError):
        record_attempt(path, "F1", "x", "great")
    with pytest.raises(LedgerError):
        record_attempt(path, "F1", "  ", "kept")
    assert raw(path) == before


def seed_history(path, history, total_attempts=0):
    data = json.loads(path.read_text())
    data["history"] = history
    data["total_attempts"] = total_attempts
    path.write_text(json.dumps(data))


def test_status_stops_at_cap(path):
    ingest(path, [finding()])
    seed_history(path, [1], total_attempts=5)
    assert status(load_ledger(path)) == {"stop": True, "reason": "cap", "next": "F1"}


def test_status_stops_bar_clear(path):
    ingest(path, [finding(severity="P3")])
    assert status(load_ledger(path)) == {"stop": True, "reason": "bar-clear", "next": None}


def test_status_stops_no_progress_after_two_flat_iterations(path):
    ingest(path, [finding()])
    seed_history(path, [3, 3, 3])
    assert status(load_ledger(path))["reason"] == "no-progress"
    seed_history(path, [2, 3, 4])
    assert status(load_ledger(path))["reason"] == "no-progress"


def test_status_needs_three_history_entries_for_no_progress(path):
    ingest(path, [finding()])
    seed_history(path, [3, 3])
    assert status(load_ledger(path)) == {"stop": False, "reason": None, "next": "F1"}


def test_status_continues_when_count_drops(path):
    ingest(path, [finding()])
    seed_history(path, [4, 4, 3])
    assert status(load_ledger(path)) == {"stop": False, "reason": None, "next": "F1"}


def test_report_lists_unresolved_with_evidence_and_needs_you(path):
    ingest(path, [
        finding(title="Cancel too loud", before="Cancel filled"),
        finding(title="Footer crushed", severity="P2"),
        finding(title="Pick a goal", kind="intent"),
        finding(title="Spacing", severity="P2"),
    ])
    record_attempt(path, "F1", "quiet cancel", "gate-failed")
    record_attempt(path, "F1", "remove cancel", "worse")
    record_attempt(path, "F2", "pad footer", "kept")
    set_status(path, "F2", "fixed", 1)
    out = report(load_ledger(path))
    assert "Cancel too loud" in out and "Cancel filled" in out
    assert "not a real issue or needs a different kind of fix" in out
    assert "quiet cancel" in out and "remove cancel" in out
    assert "Footer crushed" in out and "Pick a goal" in out
    assert "F1: 2" in out
    assert out.index("Fixed") < out.index("Unresolved") < out.index("Needs you")


def test_report_empty_sections_say_none(path):
    out = report(load_ledger(path))
    assert out.count("None.") == 4
