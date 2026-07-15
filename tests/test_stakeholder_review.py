from datetime import date

from openpyxl import load_workbook
from openpyxl.styles import Protection

from core.models import Confidence, Criterion, CriteriaTaxonomy, ScoreEntry, Vendor, VendorResearchCache, VendorSource
from core.render.stakeholder_workbook import HEADER_ROW, generate_workbook
from core.stakeholder_review import _column_map, merge, populate, snapshot, validate_workbook


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


def _generate_two_stakeholders(tmp_path, filename="master.xlsx"):
    out_path = tmp_path / filename
    taxonomy = _taxonomy()
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="ev2", confidence=Confidence.PAPER))
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[("Jane Doe", "DAST SME"), (None, "Dev Lead")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def _row_for(ws, cols, criterion_id):
    crit_col = cols["_criterion_id"]
    for r in range(4, ws.max_row + 1):
        if ws[f"{crit_col}{r}"].value == criterion_id:
            return r
    raise AssertionError(f"row for {criterion_id} not found")


def test_merge_fills_blank_master_cells_from_a_valid_returned_copy(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Score']}{row}"] = 4.5
    copy_ws[f"{cols['Jane Doe (DAST SME) Rationale']}{row}"] = "Confirmed with vendor demo"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "merged 1 cell" in summary

    master_ws = load_workbook(master_path)["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    assert master_ws[f"{mcols['Jane Doe (DAST SME) Score']}{mrow}"].value == 4.5


def test_merge_flags_conflict_without_overwriting(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    master_wb = load_workbook(master_path)
    master_ws = master_wb["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    master_ws[f"{mcols['Jane Doe (DAST SME) Score']}{mrow}"] = 3.0
    master_wb.save(master_path)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Score']}{row}"] = 4.5
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 conflict" in summary
    assert load_workbook(master_path)["v1"][f"{mcols['Jane Doe (DAST SME) Score']}{mrow}"].value == 3.0


def _generate_one_stakeholder(tmp_path, filename):
    out_path = tmp_path / filename
    taxonomy = _taxonomy()
    vendor = Vendor(id="v1", name="Vendor One", source=VendorSource.DISCOVERED)
    vendor.scores.append(ScoreEntry(criterion_id="c1", score=4.0, evidence="ev1", confidence=Confidence.PAPER))
    vendor.scores.append(ScoreEntry(criterion_id="c2", score=2.0, evidence="ev2", confidence=Confidence.PAPER))
    generate_workbook(
        taxonomy=taxonomy,
        vendors=[vendor],
        stakeholders=[(None, "DAST SME")],
        pending_criteria={},
        research_caches={"v1": VendorResearchCache(vendor_id="v1")},
        out_path=out_path,
    )
    return out_path


def test_merge_flags_unrecognized_stakeholder_column_and_does_not_write_it(tmp_path):
    master_path = _generate_one_stakeholder(tmp_path, "master.xlsx")
    copy_path = _generate_one_stakeholder(tmp_path, "copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    # Simulate a stakeholder in the returned copy that master has no header for,
    # by writing new header cells directly into row 3 and giving it a value.
    header_row = copy_ws[HEADER_ROW]
    next_col = len(header_row) + 1
    copy_ws.cell(row=HEADER_ROW, column=next_col, value="New Reviewer Score")
    copy_ws.cell(row=HEADER_ROW, column=next_col + 1, value="New Reviewer Dispute?")
    copy_ws.cell(row=HEADER_ROW, column=next_col + 2, value="New Reviewer Rationale")
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws.cell(row=row, column=next_col, value=4.0)
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "New Reviewer Score" in summary

    master_ws = load_workbook(master_path)["v1"]
    master_header = [c.value for c in master_ws[HEADER_ROW]]
    assert "New Reviewer Score" not in master_header
    assert "New Reviewer Dispute?" not in master_header
    assert "New Reviewer Rationale" not in master_header


def test_merge_flags_conflict_on_rationale_alone_when_score_is_blank(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    master_wb = load_workbook(master_path)
    master_ws = master_wb["v1"]
    mcols = _column_map(master_ws)
    mrow = _row_for(master_ws, mcols, "c1")
    # Master's Score is left blank, but Rationale already has a note.
    master_ws[f"{mcols['Jane Doe (DAST SME) Rationale']}{mrow}"] = "already had a note"
    master_wb.save(master_path)

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    # Returned copy has a different, non-blank Rationale for the same row; Score stays blank.
    copy_ws[f"{cols['Jane Doe (DAST SME) Rationale']}{row}"] = "a totally different note"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "1 conflict" in summary

    master_after = load_workbook(master_path)["v1"]
    assert master_after[f"{mcols['Jane Doe (DAST SME) Rationale']}{mrow}"].value == "already had a note"


def test_merge_flags_invalid_score_and_dispute_without_rationale(tmp_path):
    master_path = _generate_two_stakeholders(tmp_path, "master.xlsx")
    copy_path = _generate_two_stakeholders(tmp_path, "jane-copy.xlsx")

    copy_wb = load_workbook(copy_path)
    copy_ws = copy_wb["v1"]
    cols = _column_map(copy_ws)
    row = _row_for(copy_ws, cols, "c1")
    copy_ws[f"{cols['Jane Doe (DAST SME) Score']}{row}"] = 9.0
    row2 = _row_for(copy_ws, cols, "c2")
    copy_ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row2}"] = "Y"
    copy_wb.save(copy_path)

    summary = merge(master_path, copy_path)
    assert "2 invalid" in summary


def test_validate_workbook_flags_dispute_without_rationale_and_invalid_score(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    wb = load_workbook(file_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c1")
    ws[f"{cols['Jane Doe (DAST SME) Dispute?']}{row}"] = "Y"
    row2 = _row_for(ws, cols, "c2")
    ws[f"{cols['Dev Lead Score']}{row2}"] = 9.0
    wb.save(file_path)

    issues = validate_workbook(file_path)
    assert len(issues) == 2


def test_validate_workbook_returns_empty_list_for_clean_file(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    assert validate_workbook(file_path) == []


def test_validate_workbook_flags_pending_row_with_data_entered(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    wb = load_workbook(out_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c2")
    # Tamper: enter a score on the pending row without touching its lock.
    ws[f"{cols['DAST SME Score']}{row}"] = 3.0
    wb.save(out_path)

    issues = validate_workbook(out_path)
    assert any("tampered" in issue for issue in issues)


def test_validate_workbook_flags_pending_row_with_lock_removed(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    wb = load_workbook(out_path)
    ws = wb["v1"]
    cols = _column_map(ws)
    row = _row_for(ws, cols, "c2")
    # Tamper: remove the lock but leave the cell blank (no data entered).
    ws[f"{cols['DAST SME Score']}{row}"].protection = Protection(locked=False)
    wb.save(out_path)

    issues = validate_workbook(out_path)
    assert any("tampered" in issue for issue in issues)


def test_validate_workbook_does_not_flag_untouched_pending_row(tmp_path):
    out_path = _generate_with_c2_pending(tmp_path)
    issues = validate_workbook(out_path)
    assert not any("tampered" in issue for issue in issues)


def test_snapshot_copies_file_into_archive_dir(tmp_path):
    file_path = _generate_two_stakeholders(tmp_path, "review.xlsx")
    archive_dir = tmp_path / "archive"
    result = snapshot(file_path, "v1", archive_dir, label="baseline")
    assert result.exists()
    assert result.parent == archive_dir
    assert "v1" in result.name
    assert "baseline" in result.name
    assert result.read_bytes() == file_path.read_bytes()
