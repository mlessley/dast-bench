from openpyxl import load_workbook

from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorResearchCache, VendorSource
from core.render.stakeholder_workbook import generate_workbook
from core.stakeholder_review import populate


def _taxonomy():
    return CriteriaTaxonomy(
        criteria=[
            Criterion(id="c1", category="Coverage", name="Coverage One", description="d", weight=60, rubric="r"),
            Criterion(id="c2", category="DX", name="DX One", description="d", weight=40, rubric="r"),
        ]
    )


def _vendor_with_hands_on_c2():
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=1.0, evidence="paper guess", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=3.5, evidence="hands-on: 7/10 detected", confidence=Confidence.HANDS_ON))
    return vendor


def _generate_with_c2_pending(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={"v1": {"c2"}},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def test_populate_fills_pending_row_and_unlocks_it(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    vendor = _vendor_with_hands_on_c2()
    summary = populate(vendor, out_path)
    assert "populated 1" in summary

    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    pending_col = header.index("_pending") + 1
    stakeholder_score_col = header.index("DAST SME Score") + 1
    stakeholder_dispute_col = header.index("DAST SME Dispute?") + 1
    stakeholder_rationale_col = header.index("DAST SME Rationale") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    assert ws.cell(row=row, column=score_col).value == 3.5
    assert ws.cell(row=row, column=evidence_col).value == "hands-on: 7/10 detected"
    assert ws.cell(row=row, column=pending_col).value == 0
    assert ws.cell(row=row, column=stakeholder_score_col).protection.locked is False
    assert ws.cell(row=row, column=stakeholder_dispute_col).protection.locked is False
    assert ws.cell(row=row, column=stakeholder_rationale_col).protection.locked is False


def test_populate_leaves_stakeholder_entered_cells_untouched(tmp_path):
    # A stakeholder may pre-fill a Dispute/Rationale note on a PENDING row
    # (e.g. criterion c2) before dast-scan results land. populate() must
    # fill in that same row's Automated Score/Evidence without disturbing
    # the stakeholder-entered cell.
    out_path = _generate_with_c2_pending(tmp_path)
    ws = load_workbook(out_path)["v1"]
    header = [c.value for c in ws[3]]
    crit_id_col = header.index("_criterion_id") + 1
    rationale_col = header.index("DAST SME Rationale") + 1
    score_col = header.index("Automated Score") + 1
    evidence_col = header.index("Automated Evidence") + 1
    row = next(r for r in range(4, ws.max_row + 1) if ws.cell(row=r, column=crit_id_col).value == "c2")
    ws.cell(row=row, column=rationale_col).value = "pre-filled before scan results landed"
    wb = ws.parent
    wb.save(out_path)

    vendor = _vendor_with_hands_on_c2()
    populate(vendor, out_path)

    ws2 = load_workbook(out_path)["v1"]
    assert ws2.cell(row=row, column=rationale_col).value == "pre-filled before scan results landed"
    assert ws2.cell(row=row, column=score_col).value == 3.5
    assert ws2.cell(row=row, column=evidence_col).value == "hands-on: 7/10 detected"


def test_populate_is_a_no_op_when_vendor_has_no_pending_rows(tmp_path):
    out_path = tmp_path / "review.xlsx"
    taxonomy = _taxonomy()
    vendor = _vendor_with_hands_on_c2()
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    summary = populate(vendor, out_path)
    assert "populated 0" in summary
