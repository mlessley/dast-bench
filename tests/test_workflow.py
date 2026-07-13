from core.models import (
    Confidence,
    Criterion,
    CriteriaTaxonomy,
    ScoreEntry,
    Vendor,
    VendorSource,
    VendorStatus,
)
from core.workflow import SKILLS, phase_report


def _taxonomy(*weights: float) -> CriteriaTaxonomy:
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id=f"c{i}", category="Coverage", name=f"n{i}", description="d", weight=w, rubric="r")
            for i, w in enumerate(weights)
        ]
    )


def _scored_vendor(vendor_id: str, criterion_ids: list[str], status: VendorStatus = VendorStatus.CANDIDATE) -> Vendor:
    vendor = Vendor(id=vendor_id, name=vendor_id, source=VendorSource.DISCOVERED, status=status)
    for cid in criterion_ids:
        vendor.scores.append(ScoreEntry(criterion_id=cid, score=3, evidence="e", confidence=Confidence.PAPER))
    return vendor


def test_skills_table_has_all_six_skills_in_order():
    assert [s["name"] for s in SKILLS] == [
        "dast-criteria",
        "dast-discovery",
        "dast-shortlist",
        "dast-onboard-tool",
        "dast-scan",
        "dast-report",
    ]
    for skill in SKILLS:
        assert skill["purpose"] and skill["reads"] and skill["writes"]


def test_phase_report_criteria_not_started():
    lines = phase_report(CriteriaTaxonomy(), [])
    assert "[ ] Criteria      not started" in lines


def test_phase_report_criteria_invalid_weights():
    lines = phase_report(_taxonomy(50), [])
    assert "[!] Criteria      1 criteria, weights invalid" in lines


def test_phase_report_criteria_done():
    lines = phase_report(_taxonomy(100), [])
    assert "[x] Criteria      1 criteria, weights sum to 100" in lines


def test_phase_report_discovery_empty():
    lines = phase_report(_taxonomy(100), [])
    assert "[ ] Discovery     no candidates yet" in lines


def test_phase_report_discovery_counts_seeded_and_discovered():
    v1 = Vendor(id="v1", name="v1", source=VendorSource.SEEDED)
    v2 = Vendor(id="v2", name="v2", source=VendorSource.DISCOVERED)
    lines = phase_report(_taxonomy(100), [v1, v2])
    assert "[x] Discovery     2 candidates (1 seeded, 1 discovered)" in lines


def test_phase_report_shortlist_partial():
    taxonomy = _taxonomy(50, 50)
    vendor = _scored_vendor("v1", ["c0"])
    lines = phase_report(taxonomy, [vendor])
    assert "[ ] Shortlist     0/1 candidates fully scored" in lines


def test_phase_report_shortlist_scored_pending_decision():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.CANDIDATE)
    lines = phase_report(taxonomy, [vendor])
    assert "[ ] Shortlist     scored, 1 finalist decision(s) pending" in lines


def test_phase_report_shortlist_done():
    taxonomy = _taxonomy(100)
    v1 = _scored_vendor("v1", ["c0"], status=VendorStatus.FINALIST)
    v2 = _scored_vendor("v2", ["c0"], status=VendorStatus.REJECTED)
    lines = phase_report(taxonomy, [v1, v2])
    assert "[x] Shortlist     2/2 scored, 1 finalists, 1 rejected" in lines


def test_phase_report_hands_on_scan_no_finalists():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.REJECTED)
    lines = phase_report(taxonomy, [vendor])
    assert "[ ] Hands-on scan no finalists yet" in lines


def test_phase_report_hands_on_scan_partial():
    taxonomy = _taxonomy(100)
    v1 = _scored_vendor("v1", ["c0"], status=VendorStatus.FINALIST)
    v2 = _scored_vendor("v2", ["c0"], status=VendorStatus.EVALUATED)
    lines = phase_report(taxonomy, [v1, v2])
    assert "[ ] Hands-on scan 1/2 finalists evaluated" in lines


def test_phase_report_hands_on_scan_done():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.EVALUATED)
    lines = phase_report(taxonomy, [vendor])
    assert "[x] Hands-on scan 1/1 finalists evaluated" in lines


def test_next_action_recommends_criteria_when_missing():
    lines = phase_report(CriteriaTaxonomy(), [])
    assert any(line.startswith("Next: run dast-criteria --") for line in lines)


def test_next_action_recommends_discovery_when_no_vendors():
    lines = phase_report(_taxonomy(100), [])
    assert any(line.startswith("Next: run dast-discovery --") for line in lines)


def test_next_action_recommends_shortlist_when_scores_missing():
    taxonomy = _taxonomy(50, 50)
    vendor = _scored_vendor("v1", ["c0"])
    lines = phase_report(taxonomy, [vendor])
    assert any(line.startswith("Next: run dast-shortlist --") for line in lines)


def test_next_action_recommends_shortlist_when_decisions_pending():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.CANDIDATE)
    lines = phase_report(taxonomy, [vendor])
    assert any(line.startswith("Next: run dast-shortlist --") for line in lines)


def test_next_action_recommends_scan_when_finalists_pending():
    taxonomy = _taxonomy(100)
    vendor = _scored_vendor("v1", ["c0"], status=VendorStatus.FINALIST)
    lines = phase_report(taxonomy, [vendor])
    assert any(line.startswith("Next: run dast-scan (or dast-onboard-tool if not CI-wired) --") for line in lines)


def test_next_action_recommends_report_when_everything_settled():
    taxonomy = _taxonomy(100)
    v1 = _scored_vendor("v1", ["c0"], status=VendorStatus.EVALUATED)
    v2 = _scored_vendor("v2", ["c0"], status=VendorStatus.REJECTED)
    lines = phase_report(taxonomy, [v1, v2])
    assert any(line.startswith("Next: everything's current -- run dast-report --") for line in lines)
